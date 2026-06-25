import uuid
from typing import Optional, Any

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, and_

from app.models.strategy import Strategy, StrategyStatus
from app.models.backtest import Backtest
from engine.strategy_builder.strategy_ir import StrategyIR


class StrategyNotFoundError(HTTPException):
    def __init__(self):
        super().__init__(status_code=404, detail="Strategy not found")


class StrategyValidationError(HTTPException):
    def __init__(self, detail: str = "Invalid strategy data"):
        super().__init__(status_code=422, detail=detail)


class UnauthorizedAccessError(HTTPException):
    def __init__(self, detail: str = "Not authorized to access this strategy"):
        super().__init__(status_code=403, detail=detail)


class StrategyService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self, user_id: uuid.UUID, data: dict[str, Any]
    ) -> Strategy:
        ir_json = data.get("ir_json")
        if ir_json is not None:
            try:
                strategy_ir = StrategyIR.from_dict(ir_json)
                errors = strategy_ir.validate()
                if errors:
                    raise StrategyValidationError(
                        f"IR validation failed: {'; '.join(errors)}"
                    )
            except Exception as exc:
                if isinstance(exc, StrategyValidationError):
                    raise
                raise StrategyValidationError(f"Invalid IR format: {str(exc)}")

        strategy = Strategy(
            user_id=user_id,
            name=data["name"],
            description=data.get("description"),
            ir_json=ir_json,
            config=data.get("config"),
            status=data.get("status", StrategyStatus.DRAFT),
        )
        self.db.add(strategy)
        await self.db.commit()
        await self.db.refresh(strategy)
        return strategy

    async def get_by_id(
        self, strategy_id: uuid.UUID, user_id: Optional[uuid.UUID] = None
    ) -> Optional[Strategy]:
        result = await self.db.execute(
            select(Strategy).where(Strategy.id == strategy_id)
        )
        strategy = result.scalar_one_or_none()
        if strategy is None:
            return None
        if user_id is not None and strategy.user_id != user_id:
            raise UnauthorizedAccessError()
        return strategy

    async def list_by_user(
        self,
        user_id: uuid.UUID,
        filters: Optional[dict[str, Any]] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Strategy]:
        query = select(Strategy).where(Strategy.user_id == user_id)

        if filters:
            if "status" in filters:
                query = query.where(Strategy.status == filters["status"])
            if "name" in filters:
                query = query.where(
                    Strategy.name.ilike(f"%{filters['name']}%")
                )

        query = query.order_by(desc(Strategy.created_at)).offset(skip).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def update(
        self, strategy_id: uuid.UUID, user_id: uuid.UUID, data: dict[str, Any]
    ) -> Strategy:
        strategy = await self.get_by_id(strategy_id, user_id)
        if strategy is None:
            raise StrategyNotFoundError()

        if "ir_json" in data and data["ir_json"] is not None:
            try:
                strategy_ir = StrategyIR.from_dict(data["ir_json"])
                errors = strategy_ir.validate()
                if errors:
                    raise StrategyValidationError(
                        f"IR validation failed: {'; '.join(errors)}"
                    )
            except Exception as exc:
                if isinstance(exc, StrategyValidationError):
                    raise
                raise StrategyValidationError(f"Invalid IR format: {str(exc)}")

        for key, value in data.items():
            if hasattr(strategy, key):
                setattr(strategy, key, value)

        await self.db.commit()
        await self.db.refresh(strategy)
        return strategy

    async def delete(self, strategy_id: uuid.UUID, user_id: uuid.UUID) -> None:
        strategy = await self.get_by_id(strategy_id, user_id)
        if strategy is None:
            raise StrategyNotFoundError()

        # Delete all associated backtests (cascade is set in model, but explicit
        # delete ensures Celery tasks are also revoked if needed)
        result = await self.db.execute(
            select(Backtest).where(Backtest.strategy_id == strategy_id)
        )
        backtests = result.scalars().all()
        for backtest in backtests:
            await self.db.delete(backtest)

        await self.db.delete(strategy)
        await self.db.commit()

    async def duplicate(
        self, strategy_id: uuid.UUID, user_id: uuid.UUID
    ) -> Strategy:
        strategy = await self.get_by_id(strategy_id, user_id)
        if strategy is None:
            raise StrategyNotFoundError()

        new_strategy = Strategy(
            user_id=user_id,
            name=f"{strategy.name} (Copy)",
            description=strategy.description,
            ir_json=strategy.ir_json,
            config=strategy.config,
            status=StrategyStatus.DRAFT,
        )
        self.db.add(new_strategy)
        await self.db.commit()
        await self.db.refresh(new_strategy)
        return new_strategy

    async def generate_code(
        self, strategy_id: uuid.UUID, user_id: uuid.UUID, template_name: str
    ) -> str:
        strategy = await self.get_by_id(strategy_id, user_id)
        if strategy is None:
            raise StrategyNotFoundError()

        if not strategy.ir_json:
            raise StrategyValidationError("Strategy has no IR data")

        try:
            from engine.codegen.python_generator import PythonGenerator, TemplateConfig
            from engine.strategy_builder.strategy_ir import StrategyIR

            strategy_ir = StrategyIR.from_dict(strategy.ir_json)
            generator = PythonGenerator()
            config = TemplateConfig(
                template_name=f"{template_name}.py.j2"
                if not template_name.endswith(".py.j2")
                else template_name
            )
            code = generator.generate(strategy_ir, config)
            return code
        except Exception as exc:
            raise StrategyValidationError(f"Code generation failed: {str(exc)}")

    async def get_history(self, strategy_id: uuid.UUID, user_id: uuid.UUID) -> list[dict]:
        strategy = await self.get_by_id(strategy_id, user_id)
        if strategy is None:
            raise StrategyNotFoundError()

        # Simplified history: return current state with metadata
        # In production, this would query a version history table
        return [
            {
                "version": 1,
                "updated_at": strategy.updated_at.isoformat() if strategy.updated_at else None,
                "name": strategy.name,
                "status": strategy.status.value,
                "ir_hash": hash(str(strategy.ir_json)) & 0xFFFFFFFF,
            }
        ]
