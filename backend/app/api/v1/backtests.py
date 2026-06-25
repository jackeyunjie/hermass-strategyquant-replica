import uuid
from typing import Optional, Any

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.backtest import Backtest, BacktestStatus
from app.models.user import User
from app.services.backtest_service import BacktestService, BacktestNotFoundError

router = APIRouter()


class BacktestCreate(BaseModel):
    strategy_id: uuid.UUID
    config: dict = Field(default_factory=dict, description="Backtest configuration")


class BacktestConfigDetail(BaseModel):
    symbol: str = "000001.SZ"
    timeframe: str = "1d"
    start_date: str = "2020-01-01"
    end_date: str = "2024-01-01"
    initial_capital: float = 1_000_000.0
    commission_rate: float = 0.0003
    slippage: float = 0.001


class BacktestSummary(BaseModel):
    id: str
    strategy_id: str
    status: str
    created_at: str
    updated_at: str

    model_config = ConfigDict(from_attributes=True)


class BacktestStatusResponse(BaseModel):
    id: str
    status: str
    celery_status: Optional[str]
    task_id: Optional[str]
    created_at: Optional[str]
    completed_at: Optional[str]
    runtime_seconds: Optional[float]
    error_message: Optional[str]


class BacktestResultResponse(BaseModel):
    id: str
    strategy_id: str
    status: str
    config: Optional[dict]
    result: Optional[dict]
    metrics: Optional[dict]
    error_message: Optional[str]
    runtime_seconds: Optional[float]
    created_at: Optional[str]
    completed_at: Optional[str]
    updated_at: Optional[str]

    model_config = ConfigDict(from_attributes=True)


class BacktestListResponse(BaseModel):
    total: int
    items: list[BacktestSummary]


class BacktestBatchRequest(BaseModel):
    strategy_ids: list[uuid.UUID] = Field(..., min_length=1, max_length=10)
    config: dict = Field(default_factory=dict)


class BacktestBatchResponse(BaseModel):
    backtests: list[BacktestSummary]


@router.post(
    "",
    response_model=BacktestSummary,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit backtest",
    description="Submit a backtest task for a strategy. Creates DB record and dispatches to Celery.",
)
async def submit_backtest(
    payload: BacktestCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = BacktestService(db)
    backtest = await service.submit(
        strategy_id=payload.strategy_id,
        user_id=current_user.id,
        config=payload.config,
    )
    return _backtest_to_summary(backtest)


@router.get(
    "",
    response_model=BacktestListResponse,
    summary="List backtests",
    description="List backtests with pagination and status filter.",
)
async def list_backtests(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[BacktestStatus] = Query(None, description="Filter by status"),
    strategy_id: Optional[uuid.UUID] = Query(None, description="Filter by strategy"),
):
    service = BacktestService(db)
    filters: dict[str, Any] = {}
    if status:
        filters["status"] = status
    if strategy_id:
        filters["strategy_id"] = strategy_id

    skip = (page - 1) * limit
    backtests = await service.list_by_user(
        user_id=current_user.id,
        filters=filters,
        skip=skip,
        limit=limit,
    )

    items = [_backtest_to_summary(b) for b in backtests]
    return BacktestListResponse(total=len(items), items=items)


@router.get(
    "/{backtest_id}",
    response_model=BacktestResultResponse,
    summary="Get backtest result",
    description="Get full backtest result including equity curve, trades, and metrics.",
)
async def get_backtest(
    backtest_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = BacktestService(db)
    backtest = await service.get_result(backtest_id, current_user.id)
    if backtest is None:
        raise HTTPException(status_code=404, detail="Backtest not found")
    return _backtest_to_result(backtest)


@router.get(
    "/{backtest_id}/status",
    response_model=BacktestStatusResponse,
    summary="Get backtest status",
    description="Get backtest status for polling. Lightweight endpoint.",
)
async def get_backtest_status(
    backtest_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = BacktestService(db)
    try:
        status_data = await service.get_status(backtest_id)
        return BacktestStatusResponse(**status_data)
    except BacktestNotFoundError:
        raise HTTPException(status_code=404, detail="Backtest not found")


@router.delete(
    "/{backtest_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete backtest",
    description="Delete a backtest task and its results.",
)
async def delete_backtest(
    backtest_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = BacktestService(db)
    try:
        await service.delete(backtest_id, current_user.id)
    except BacktestNotFoundError:
        raise HTTPException(status_code=404, detail="Backtest not found")
    return None


@router.post(
    "/{backtest_id}/cancel",
    response_model=BacktestStatusResponse,
    summary="Cancel backtest",
    description="Cancel a pending or running backtest task.",
)
async def cancel_backtest(
    backtest_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = BacktestService(db)
    try:
        backtest = await service.cancel(backtest_id, current_user.id)
        status_data = await service.get_status(backtest_id)
        return BacktestStatusResponse(**status_data)
    except BacktestNotFoundError:
        raise HTTPException(status_code=404, detail="Backtest not found")


@router.post(
    "/{backtest_id}/rerun",
    response_model=BacktestSummary,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Rerun backtest",
    description="Create a new backtest with the same configuration.",
)
async def rerun_backtest(
    backtest_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = BacktestService(db)
    try:
        backtest = await service.rerun(backtest_id, current_user.id)
        return _backtest_to_summary(backtest)
    except BacktestNotFoundError:
        raise HTTPException(status_code=404, detail="Backtest not found")


@router.post(
    "/batch",
    response_model=BacktestBatchResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Batch submit backtests",
    description="Submit backtests for multiple strategies simultaneously.",
)
async def batch_submit_backtests(
    payload: BacktestBatchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = BacktestService(db)
    backtests = await service.submit_batch(
        strategy_ids=payload.strategy_ids,
        user_id=current_user.id,
        config=payload.config,
    )
    return BacktestBatchResponse(
        backtests=[_backtest_to_summary(b) for b in backtests]
    )


def _backtest_to_summary(backtest: Backtest) -> BacktestSummary:
    return BacktestSummary(
        id=str(backtest.id),
        strategy_id=str(backtest.strategy_id),
        status=backtest.status.value,
        created_at=backtest.created_at.isoformat() if backtest.created_at else "",
        updated_at=backtest.updated_at.isoformat() if backtest.updated_at else "",
    )


def _backtest_to_result(backtest: Backtest) -> BacktestResultResponse:
    return BacktestResultResponse(
        id=str(backtest.id),
        strategy_id=str(backtest.strategy_id),
        status=backtest.status.value,
        config=backtest.config,
        result=backtest.result,
        metrics=backtest.metrics,
        error_message=backtest.error_message,
        runtime_seconds=backtest.runtime_seconds,
        created_at=backtest.created_at.isoformat() if backtest.created_at else None,
        completed_at=backtest.completed_at.isoformat() if backtest.completed_at else None,
        updated_at=backtest.updated_at.isoformat() if backtest.updated_at else None,
    )
