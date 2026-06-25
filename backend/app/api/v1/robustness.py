import uuid
from typing import Optional, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User

router = APIRouter()


class MonteCarloRequest(BaseModel):
    strategy_id: uuid.UUID
    backtest_id: Optional[uuid.UUID] = None
    method: str = Field(
        default="shuffle_trades",
        pattern="^(shuffle_trades|skip_trades|param_perturb|data_noise|all)$",
    )
    config: dict = Field(default_factory=dict)
    n_simulations: int = Field(default=1000, ge=100, le=10000)


class MonteCarloResponse(BaseModel):
    task_id: str
    status: str
    message: str


class WalkForwardRequest(BaseModel):
    strategy_id: uuid.UUID
    data_config: dict = Field(default_factory=dict)
    wfo_config: dict = Field(default_factory=dict)


class WalkForwardResponse(BaseModel):
    task_id: str
    status: str
    message: str


class OverfittingRequest(BaseModel):
    strategy_id: uuid.UUID
    backtest_id: Optional[uuid.UUID] = None
    n_splits: int = Field(default=4, ge=2, le=10)


class OverfittingResponse(BaseModel):
    task_id: str
    status: str
    message: str


class RobustnessReport(BaseModel):
    id: str
    report_type: str
    status: str
    result: Optional[dict]
    created_at: str


@router.post(
    "/monte-carlo",
    response_model=MonteCarloResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Monte Carlo simulation",
    description="Run Monte Carlo simulation to assess strategy robustness.",
)
async def monte_carlo(
    payload: MonteCarloRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # TODO: dispatch to Celery task
    from app.tasks.backtest_tasks import run_monte_carlo_task

    task = run_monte_carlo_task.delay(
        str(payload.strategy_id),
        str(payload.backtest_id) if payload.backtest_id else None,
        payload.method,
        payload.config,
    )
    return MonteCarloResponse(
        task_id=task.id, status="pending", message="Monte Carlo simulation queued"
    )


@router.post(
    "/walk-forward",
    response_model=WalkForwardResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Walk-Forward Analysis",
    description="Run Walk-Forward Analysis (WFA) to detect overfitting.",
)
async def walk_forward(
    payload: WalkForwardRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.tasks.backtest_tasks import run_walk_forward_task

    task = run_walk_forward_task.delay(
        str(payload.strategy_id),
        payload.data_config,
        payload.wfo_config,
    )
    return WalkForwardResponse(
        task_id=task.id, status="pending", message="Walk-Forward analysis queued"
    )


@router.post(
    "/overfitting",
    response_model=OverfittingResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Overfitting detection",
    description="Run PBO/DSR/PSR overfitting detection tests.",
)
async def overfitting(
    payload: OverfittingRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.tasks.backtest_tasks import run_overfitting_task

    task = run_overfitting_task.delay(
        str(payload.strategy_id),
        str(payload.backtest_id) if payload.backtest_id else None,
        payload.n_splits,
    )
    return OverfittingResponse(
        task_id=task.id, status="pending", message="Overfitting detection queued"
    )


@router.get(
    "/report/{report_id}",
    response_model=RobustnessReport,
    summary="Get robustness report",
    description="Get the result of a robustness test by report/task ID.",
)
async def get_robustness_report(
    report_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # TODO: query result from DB or Celery result backend
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Robustness report storage not yet implemented",
    )
