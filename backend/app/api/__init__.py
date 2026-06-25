from fastapi import APIRouter

from app.api.v1 import (
    ai,
    auth,
    backtests,
    data,
    fuzzy,
    indicator_marketplace,
    optimizer,
    robustness,
    strategies,
)

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(
    strategies.router, prefix="/strategies", tags=["strategies"]
)
api_router.include_router(
    backtests.router, prefix="/backtests", tags=["backtests"]
)
api_router.include_router(data.router, prefix="/data", tags=["data"])
api_router.include_router(
    robustness.router, prefix="/robustness", tags=["robustness"]
)
api_router.include_router(
    optimizer.router, prefix="/optimizer", tags=["optimizer"]
)
api_router.include_router(ai.router, prefix="/ai", tags=["ai"])
api_router.include_router(fuzzy.router, prefix="/fuzzy", tags=["fuzzy"])
api_router.include_router(
    indicator_marketplace.router,
    prefix="/indicator-marketplace",
    tags=["indicator-marketplace"],
)
