import uuid
from typing import Optional, Any

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.strategy import Strategy, StrategyStatus
from app.models.user import User
from app.services.strategy_service import StrategyService, StrategyNotFoundError

router = APIRouter()


class StrategyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    ir_json: Optional[dict] = None
    config: Optional[dict] = None


class StrategyUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    ir_json: Optional[dict] = None
    config: Optional[dict] = None
    status: Optional[StrategyStatus] = None


class StrategySummary(BaseModel):
    id: str
    user_id: str
    name: str
    status: str
    created_at: str
    updated_at: str

    model_config = ConfigDict(from_attributes=True)


class StrategyResponse(BaseModel):
    id: str
    user_id: str
    name: str
    description: Optional[str]
    status: str
    ir_json: Optional[dict]
    config: Optional[dict]
    created_at: str
    updated_at: str

    model_config = ConfigDict(from_attributes=True)


class StrategyListResponse(BaseModel):
    total: int
    items: list[StrategySummary]


class StrategyDuplicateResponse(BaseModel):
    id: str
    name: str
    status: str


class GenerateCodeRequest(BaseModel):
    template_name: str = Field(..., min_length=1)


class GenerateCodeResponse(BaseModel):
    code: str
    template_name: str


class StrategyHistoryResponse(BaseModel):
    version: int
    updated_at: str
    name: str
    status: str
    ir_hash: int


@router.post(
    "",
    response_model=StrategyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create strategy",
    description="Create a new trading strategy with IR JSON.",
)
async def create_strategy(
    payload: StrategyCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = StrategyService(db)
    strategy = await service.create(
        user_id=current_user.id,
        data=payload.model_dump(exclude_unset=True),
    )
    return _strategy_to_response(strategy)


@router.get(
    "",
    response_model=StrategyListResponse,
    summary="List strategies",
    description="List user's strategies with pagination, search, and status filter.",
)
async def list_strategies(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None, description="Search by name"),
    status: Optional[StrategyStatus] = Query(None, description="Filter by status"),
):
    service = StrategyService(db)
    filters: dict[str, Any] = {}
    if search:
        filters["name"] = search
    if status:
        filters["status"] = status

    skip = (page - 1) * limit
    strategies = await service.list_by_user(
        user_id=current_user.id,
        filters=filters,
        skip=skip,
        limit=limit,
    )

    items = [_strategy_to_summary(s) for s in strategies]
    return StrategyListResponse(total=len(items), items=items)


@router.get(
    "/{strategy_id}",
    response_model=StrategyResponse,
    summary="Get strategy details",
    description="Get full strategy including IR JSON and config.",
)
async def get_strategy(
    strategy_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = StrategyService(db)
    strategy = await service.get_by_id(strategy_id, current_user.id)
    if strategy is None:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return _strategy_to_response(strategy)


@router.put(
    "/{strategy_id}",
    response_model=StrategyResponse,
    summary="Update strategy",
    description="Update strategy name, description, IR JSON, or config.",
)
async def update_strategy(
    strategy_id: uuid.UUID,
    payload: StrategyUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = StrategyService(db)
    try:
        strategy = await service.update(
            strategy_id,
            current_user.id,
            payload.model_dump(exclude_unset=True),
        )
        return _strategy_to_response(strategy)
    except StrategyNotFoundError:
        raise HTTPException(status_code=404, detail="Strategy not found")


@router.delete(
    "/{strategy_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete strategy",
    description="Delete strategy and all associated backtests.",
)
async def delete_strategy(
    strategy_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = StrategyService(db)
    try:
        await service.delete(strategy_id, current_user.id)
    except StrategyNotFoundError:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return None


@router.post(
    "/{strategy_id}/duplicate",
    response_model=StrategyDuplicateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Duplicate strategy",
    description="Create a copy of an existing strategy with '(Copy)' suffix.",
)
async def duplicate_strategy(
    strategy_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = StrategyService(db)
    try:
        new_strategy = await service.duplicate(strategy_id, current_user.id)
        return StrategyDuplicateResponse(
            id=str(new_strategy.id),
            name=new_strategy.name,
            status=new_strategy.status.value,
        )
    except StrategyNotFoundError:
        raise HTTPException(status_code=404, detail="Strategy not found")


@router.post(
    "/generate-code",
    response_model=GenerateCodeResponse,
    summary="Generate strategy code",
    description="Generate Python code from strategy IR using template.",
)
async def generate_code(
    payload: GenerateCodeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Note: This endpoint requires strategy_id in the payload for simplicity
    # In a real API, you'd use /strategies/{id}/generate-code
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Use /strategies/{id}/generate-code instead",
    )


@router.post(
    "/{strategy_id}/generate-code",
    response_model=GenerateCodeResponse,
    summary="Generate strategy code",
    description="Generate Python code from strategy IR using specified template.",
)
async def generate_strategy_code(
    strategy_id: uuid.UUID,
    payload: GenerateCodeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = StrategyService(db)
    try:
        code = await service.generate_code(
            strategy_id, current_user.id, payload.template_name
        )
        return GenerateCodeResponse(code=code, template_name=payload.template_name)
    except StrategyNotFoundError:
        raise HTTPException(status_code=404, detail="Strategy not found")


@router.get(
    "/{strategy_id}/history",
    response_model=list[StrategyHistoryResponse],
    summary="Strategy history",
    description="Get simplified version history for a strategy.",
)
async def get_strategy_history(
    strategy_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = StrategyService(db)
    try:
        history = await service.get_history(strategy_id, current_user.id)
        return [StrategyHistoryResponse(**h) for h in history]
    except StrategyNotFoundError:
        raise HTTPException(status_code=404, detail="Strategy not found")


def _strategy_to_summary(strategy: Strategy) -> StrategySummary:
    return StrategySummary(
        id=str(strategy.id),
        user_id=str(strategy.user_id),
        name=strategy.name,
        status=strategy.status.value,
        created_at=strategy.created_at.isoformat() if strategy.created_at else "",
        updated_at=strategy.updated_at.isoformat() if strategy.updated_at else "",
    )


def _strategy_to_response(strategy: Strategy) -> StrategyResponse:
    return StrategyResponse(
        id=str(strategy.id),
        user_id=str(strategy.user_id),
        name=strategy.name,
        description=strategy.description,
        status=strategy.status.value,
        ir_json=strategy.ir_json,
        config=strategy.config,
        created_at=strategy.created_at.isoformat() if strategy.created_at else "",
        updated_at=strategy.updated_at.isoformat() if strategy.updated_at else "",
    )
