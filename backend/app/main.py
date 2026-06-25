import sys
from pathlib import Path
# Add project root to sys.path so the backend can import the engine module
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from contextlib import asynccontextmanager
import time
import uuid as uuid_module

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.exc import IntegrityError

from app.api import api_router
from app.core.config import get_settings
from app.core.database import engine, check_db_connection, init_timescaledb
from app.models import Base

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create tables if not exists (dev convenience)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        # Initialize TimescaleDB extensions
        try:
            await init_timescaledb()
        except Exception:
            pass  # TimescaleDB may not be available in all environments
    except Exception:
        pass  # Database may not be available in dev/test environments
    
    yield
    # Shutdown
    try:
        await engine.dispose()
    except Exception:
        pass


app = FastAPI(
    title=settings.APP_NAME,
    description="Hermass StrategyQuant Replica API - Quantitative strategy backtesting and optimization platform",
    version="1.0.0",
    debug=settings.DEBUG,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    openapi_tags=[
        {"name": "auth", "description": "Authentication endpoints"},
        {"name": "strategies", "description": "Strategy CRUD and code generation"},
        {"name": "backtests", "description": "Backtest task management"},
        {"name": "data", "description": "Market data management"},
        {"name": "robustness", "description": "Robustness testing (Monte Carlo, WFO, Overfitting)"},
        {"name": "optimizer", "description": "Parameter optimization"},
        {"name": "ai", "description": "Results AI diagnostics and recommendations"},
        {"name": "fuzzy", "description": "Fuzzy Logic strategy generation"},
        {"name": "indicator-marketplace", "description": "Custom indicator marketplace"},
        {"name": "health", "description": "Health check endpoints"},
    ],
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    """Log all requests with timing and request ID."""
    request_id = str(uuid_module.uuid4())
    request.state.request_id = request_id
    start_time = time.time()
    
    response = await call_next(request)
    
    duration = time.time() - start_time
    response.headers["X-Request-ID"] = request_id
    
    # Log request details
    if hasattr(app.state, "logger") or True:
        import logging
        logger = logging.getLogger("hermass.api")
        logger.info(
            "method=%s path=%s status=%d duration=%.3fs request_id=%s",
            request.method,
            request.url.path,
            response.status_code,
            duration,
            request_id,
        )
    
    return response


# Health check with dependency checks
@app.get("/health", tags=["health"], summary="Health check")
async def health_check():
    """Check API health including database connectivity."""
    import asyncio

    # Check DB with short timeout so health endpoint stays fast
    try:
        db_healthy = await asyncio.wait_for(check_db_connection(), timeout=1.0)
    except asyncio.TimeoutError:
        db_healthy = False

    # Check Redis (short timeout)
    redis_healthy = False
    try:
        import redis
        r = redis.from_url(settings.REDIS_URL, socket_connect_timeout=1)
        redis_healthy = r.ping()
    except Exception:
        pass

    # Check Celery worker availability without blocking the event loop.
    celery_healthy = False
    try:
        from app.tasks.celery_app import celery_app

        ping_result = await asyncio.wait_for(
            asyncio.to_thread(lambda: celery_app.control.ping(timeout=1.0)),
            timeout=2.0,
        )
        celery_healthy = bool(ping_result)
    except Exception:
        pass

    overall = all([db_healthy, redis_healthy, celery_healthy])
    status_code = status.HTTP_200_OK if overall else status.HTTP_503_SERVICE_UNAVAILABLE

    return JSONResponse(
        status_code=status_code,
        content={
            "status": "healthy" if overall else "degraded",
            "app": settings.APP_NAME,
            "version": "1.0.0",
            "checks": {
                "database": "ok" if db_healthy else "error",
                "redis": "ok" if redis_healthy else "error",
                "celery": "ok" if celery_healthy else "error",
            },
        },
    )


# Exception handlers
@app.exception_handler(PydanticValidationError)
async def pydantic_validation_exception_handler(request: Request, exc: PydanticValidationError):
    """Handle Pydantic validation errors."""
    errors = []
    for error in exc.errors():
        errors.append({
            "loc": error.get("loc", []),
            "msg": error.get("msg", ""),
            "type": error.get("type", ""),
        })
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": "Validation error",
            "errors": errors,
        },
    )


@app.exception_handler(IntegrityError)
async def integrity_error_exception_handler(request: Request, exc: IntegrityError):
    """Handle SQLAlchemy integrity errors (duplicate keys, etc.)."""
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={
            "detail": "Database integrity error. Resource may already exist.",
        },
    )


@app.exception_handler(ValueError)
async def value_error_exception_handler(request: Request, exc: ValueError):
    """Handle value errors."""
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": str(exc)},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global fallback exception handler."""
    import logging
    logger = logging.getLogger("hermass.api")
    logger.exception("Unhandled exception: %s", exc)
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "Internal server error",
            "request_id": getattr(request.state, "request_id", None),
        },
    )


# Register routers
app.include_router(api_router, prefix="/api/v1")
