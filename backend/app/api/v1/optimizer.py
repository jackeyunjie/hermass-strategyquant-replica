import uuid
from typing import Optional, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User

router = APIRouter()


class OptimizerRunRequest(BaseModel):
    strategy_id: uuid.UUID
    data_config: dict = Field(default_factory=dict)
    opt_config: dict = Field(default_factory=dict)


class OptimizerRunResponse(BaseModel):
    task_id: str
    status: str
    message: str
    best_params: Optional[dict] = None
    best_metric: Optional[float] = None


class WalkForwardOptRequest(BaseModel):
    strategy_id: uuid.UUID
    data_config: dict = Field(default_factory=dict)
    wfo_config: dict = Field(default_factory=dict)


class WalkForwardOptResponse(BaseModel):
    task_id: str
    status: str
    message: str
    optimal_params_trajectory: Optional[list[dict]] = None


@router.post(
    "/run",
    response_model=OptimizerRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Run parameter optimization",
    description="Run parameter optimization using Optuna TPE sampler.",
)
async def run_optimizer(
    payload: OptimizerRunRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.tasks.backtest_tasks import run_optimizer_task

    task = run_optimizer_task.delay(
        str(payload.strategy_id),
        payload.data_config,
        payload.opt_config,
    )
    return OptimizerRunResponse(
        task_id=task.id,
        status="pending",
        message="Parameter optimization queued",
    )


@router.post(
    "/walk-forward-opt",
    response_model=WalkForwardOptResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Walk-Forward optimization",
    description="Run Walk-Forward optimization with parameter trajectory.",
)
async def walk_forward_opt(
    payload: WalkForwardOptRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.tasks.backtest_tasks import run_walk_forward_opt_task

    task = run_walk_forward_opt_task.delay(
        str(payload.strategy_id),
        payload.data_config,
        payload.wfo_config,
    )
    return WalkForwardOptResponse(
        task_id=task.id,
        status="pending",
        message="Walk-Forward optimization queued",
    )
