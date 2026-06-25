from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from engine.indicators.marketplace import IndicatorMarketplace

router = APIRouter()
marketplace = IndicatorMarketplace()


class IndicatorCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=80, pattern=r"^[A-Za-z][A-Za-z0-9_]*$")
    display_name: str = Field(..., min_length=2, max_length=120)
    description: str = Field(..., min_length=5, max_length=1000)
    category: str = Field(..., min_length=1, max_length=80)
    formula: str = Field(..., min_length=3, max_length=1000)
    tags: list[str] = Field(default_factory=list)
    param_schemas: list[dict[str, Any]] = Field(default_factory=list)


class IndicatorInstallResponse(BaseModel):
    id: str
    name: str
    installed: bool
    metadata: dict[str, Any]


@router.get(
    "",
    summary="List marketplace indicators",
    description="List built-in and user-created formula indicators.",
)
async def list_indicators(
    category: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return {"items": [item.to_dict() for item in marketplace.list(category, search)]}


@router.post(
    "",
    status_code=201,
    summary="Create marketplace indicator",
    description="Create a custom formula indicator and add it to the local marketplace catalog.",
)
async def create_indicator(
    payload: IndicatorCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = marketplace.create(
        name=payload.name,
        display_name=payload.display_name,
        formula=payload.formula,
        description=payload.description,
        category=payload.category,
        author=getattr(current_user, "email", "user"),
        tags=payload.tags,
        param_schemas=payload.param_schemas,
    )
    return item.to_dict()


@router.post(
    "/{indicator_id}/install",
    response_model=IndicatorInstallResponse,
    summary="Install marketplace indicator",
    description="Install an indicator into an IndicatorRegistry-compatible runtime.",
)
async def install_indicator(
    indicator_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    indicator = marketplace.install(indicator_id)
    metadata = indicator.get_metadata()
    return {
        "id": indicator_id,
        "name": indicator.name,
        "installed": True,
        "metadata": metadata,
    }
