import uuid
from typing import Optional, Any

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func, and_

from app.models.backtest import Backtest, BacktestStatus
from app.models.strategy import Strategy
from app.tasks.celery_app import celery_app


class BacktestNotFoundError(HTTPException):
    def __init__(self):
        super().__init__(status_code=404, detail="Backtest not found")


class BacktestLimitExceededError(HTTPException):
    def __init__(self, limit: int = 10):
        super().__init__(
            status_code=429,
            detail=f"Concurrent backtest limit exceeded (max {limit})",
        )


class BacktestError(HTTPException):
    def __init__(self, detail: str = "Backtest error"):
        super().__init__(status_code=500, detail=detail)


class BacktestService:
    MAX_CONCURRENT_BACKTESTS = 10

    def __init__(self, db: AsyncSession):
        self.db = db

    async def _check_ownership(self, backtest_id: uuid.UUID, user_id: uuid.UUID) -> Backtest:
        result = await self.db.execute(
            select(Backtest)
            .join(Strategy, Backtest.strategy_id == Strategy.id)
            .where(Backtest.id == backtest_id, Strategy.user_id == user_id)
        )
        backtest = result.scalar_one_or_none()
        if backtest is None:
            raise BacktestNotFoundError()
        return backtest

    async def _count_running_backtests(self, user_id: uuid.UUID) -> int:
        result = await self.db.execute(
            select(func.count(Backtest.id))
            .join(Strategy, Backtest.strategy_id == Strategy.id)
            .where(
                Strategy.user_id == user_id,
                Backtest.status.in_([BacktestStatus.PENDING, BacktestStatus.RUNNING]),
            )
        )
        return result.scalar() or 0

    async def submit(
        self, strategy_id: uuid.UUID, user_id: uuid.UUID, config: dict[str, Any]
    ) -> Backtest:
        # Verify strategy ownership
        result = await self.db.execute(
            select(Strategy).where(Strategy.id == strategy_id)
        )
        strategy = result.scalar_one_or_none()
        if strategy is None or strategy.user_id != user_id:
            raise HTTPException(status_code=404, detail="Strategy not found")

        # Check concurrent limit
        running_count = await self._count_running_backtests(user_id)
        if running_count >= self.MAX_CONCURRENT_BACKTESTS:
            raise BacktestLimitExceededError(self.MAX_CONCURRENT_BACKTESTS)

        backtest = Backtest(
            strategy_id=strategy_id,
            status=BacktestStatus.PENDING,
            config=config,
        )
        self.db.add(backtest)
        await self.db.commit()
        await self.db.refresh(backtest)

        # Dispatch to Celery worker
        from app.tasks.backtest_tasks import run_backtest_task
        task = run_backtest_task.delay(
            str(backtest.id), str(strategy_id), config
        )

        backtest.task_id = task.id
        await self.db.commit()
        await self.db.refresh(backtest)
        return backtest

    async def submit_batch(
        self, strategy_ids: list[uuid.UUID], user_id: uuid.UUID, config: dict[str, Any]
    ) -> list[Backtest]:
        backtests = []
        for strategy_id in strategy_ids:
            backtest = await self.submit(strategy_id, user_id, config)
            backtests.append(backtest)
        return backtests

    async def get_status(self, backtest_id: uuid.UUID) -> dict[str, Any]:
        result = await self.db.execute(
            select(Backtest).where(Backtest.id == backtest_id)
        )
        backtest = result.scalar_one_or_none()
        if backtest is None:
            raise BacktestNotFoundError()

        # Also check Celery task status if applicable
        celery_status = None
        if backtest.task_id:
            try:
                celery_result = celery_app.AsyncResult(backtest.task_id)
                celery_status = celery_result.status
            except Exception:
                pass

        return {
            "id": str(backtest.id),
            "status": backtest.status.value,
            "celery_status": celery_status,
            "task_id": backtest.task_id,
            "created_at": backtest.created_at.isoformat() if backtest.created_at else None,
            "completed_at": backtest.completed_at.isoformat() if backtest.completed_at else None,
            "runtime_seconds": backtest.runtime_seconds,
            "error_message": backtest.error_message,
        }

    async def get_result(self, backtest_id: uuid.UUID, user_id: uuid.UUID) -> Backtest:
        return await self._check_ownership(backtest_id, user_id)

    async def get_by_id(
        self, backtest_id: uuid.UUID, user_id: Optional[uuid.UUID] = None
    ) -> Optional[Backtest]:
        if user_id is not None:
            return await self._check_ownership(backtest_id, user_id)
        result = await self.db.execute(
            select(Backtest).where(Backtest.id == backtest_id)
        )
        return result.scalar_one_or_none()

    async def cancel(self, backtest_id: uuid.UUID, user_id: uuid.UUID) -> Backtest:
        backtest = await self._check_ownership(backtest_id, user_id)

        if backtest.task_id and backtest.status in [
            BacktestStatus.PENDING,
            BacktestStatus.RUNNING,
        ]:
            try:
                celery_app.control.revoke(backtest.task_id, terminate=True)
            except Exception:
                pass

        backtest.status = BacktestStatus.CANCELLED
        await self.db.commit()
        await self.db.refresh(backtest)
        return backtest

    async def delete(self, backtest_id: uuid.UUID, user_id: uuid.UUID) -> None:
        backtest = await self._check_ownership(backtest_id, user_id)
        await self.db.delete(backtest)
        await self.db.commit()

    async def list_by_user(
        self,
        user_id: uuid.UUID,
        filters: Optional[dict[str, Any]] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Backtest]:
        query = (
            select(Backtest)
            .join(Strategy, Backtest.strategy_id == Strategy.id)
            .where(Strategy.user_id == user_id)
        )

        if filters:
            if "status" in filters:
                query = query.where(Backtest.status == filters["status"])
            if "strategy_id" in filters:
                query = query.where(
                    Backtest.strategy_id == filters["strategy_id"]
                )

        query = query.order_by(desc(Backtest.created_at)).offset(skip).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def rerun(self, backtest_id: uuid.UUID, user_id: uuid.UUID) -> Backtest:
        backtest = await self._check_ownership(backtest_id, user_id)

        if backtest.status in [BacktestStatus.PENDING, BacktestStatus.RUNNING]:
            raise BacktestError("Cannot rerun a pending or running backtest")

        # Create new backtest with same config
        new_backtest = Backtest(
            strategy_id=backtest.strategy_id,
            status=BacktestStatus.PENDING,
            config=backtest.config,
        )
        self.db.add(new_backtest)
        await self.db.commit()
        await self.db.refresh(new_backtest)

        from app.tasks.backtest_tasks import run_backtest_task
        task = run_backtest_task.delay(
            str(new_backtest.id), str(new_backtest.strategy_id), new_backtest.config or {}
        )
        new_backtest.task_id = task.id
        await self.db.commit()
        await self.db.refresh(new_backtest)
        return new_backtest
