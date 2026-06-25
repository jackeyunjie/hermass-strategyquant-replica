from typing import Any, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from engine.results_ai import ResultsAIAnalyzer

router = APIRouter()


class ResultsAIRequest(BaseModel):
    backtest_result: dict[str, Any] = Field(default_factory=dict)
    strategy_context: Optional[dict[str, Any]] = None
    question: Optional[str] = Field(None, max_length=500)


class ResultsAIResponse(BaseModel):
    summary: str
    regime: str
    quality_score: float
    risk_score: float
    opportunity_score: float
    insights: list[dict[str, Any]]
    suggested_actions: list[str]
    prompt_context: dict[str, Any]


@router.post(
    "/results-ai/analyze",
    response_model=ResultsAIResponse,
    summary="Analyze backtest result with Results AI",
    description="Generate deterministic AI-style diagnostics, risks, and strategy improvement actions.",
)
async def analyze_results(
    payload: ResultsAIRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    report = ResultsAIAnalyzer().analyze(
        payload.backtest_result,
        strategy_context=payload.strategy_context,
        question=payload.question,
    )
    return report.to_dict()
