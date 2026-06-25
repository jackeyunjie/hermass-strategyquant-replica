from typing import Literal, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from engine.strategy_builder.fuzzy_logic import FuzzyStrategyGenerator

router = APIRouter()


class FuzzyGenerateRequest(BaseModel):
    template: Literal["momentum", "reversal", "balanced"] = "balanced"
    name: Optional[str] = Field(None, max_length=120)
    buy_threshold: float = Field(0.62, ge=0.1, le=1.0)
    sell_threshold: float = Field(0.58, ge=0.1, le=1.0)


class FuzzyGenerateResponse(BaseModel):
    strategy_ir: dict
    frontend_graph: dict
    fuzzy_spec: dict


@router.post(
    "/generate",
    response_model=FuzzyGenerateResponse,
    summary="Generate fuzzy logic strategy",
    description="Generate a fuzzy-rule strategy and graph-compatible Strategy Builder payload.",
)
async def generate_fuzzy_strategy(
    payload: FuzzyGenerateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    generator = FuzzyStrategyGenerator()
    spec = generator.generate(
        template=payload.template,
        name=payload.name,
        buy_threshold=payload.buy_threshold,
        sell_threshold=payload.sell_threshold,
    )
    strategy_ir = generator.to_strategy_ir(spec)
    frontend_graph = generator.to_frontend_graph(spec)
    return {
        "strategy_ir": strategy_ir.to_dict(),
        "frontend_graph": frontend_graph,
        "fuzzy_spec": spec.to_dict(),
    }
