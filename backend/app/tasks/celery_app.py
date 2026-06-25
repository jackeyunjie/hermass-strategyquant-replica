import logging
import time
import uuid as uuid_module
from datetime import datetime, timezone

from celery import Celery
from sqlalchemy import create_engine, select, update
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.models.backtest import Backtest, BacktestStatus

settings = get_settings()
logger = logging.getLogger(__name__)

# Create synchronous engine for Celery tasks (workers run sync)
_sync_engine = create_engine(
    settings.DATABASE_URL.replace("+asyncpg", "+psycopg2"),
    pool_size=5,
    max_overflow=10,
)
_SyncSession = sessionmaker(bind=_sync_engine)


celery_app = Celery(
    "hermass_tasks",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks.backtest_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_always_eager=settings.CELERY_TASK_ALWAYS_EAGER,
    task_track_started=True,
    task_ignore_result=False,
    result_expires=3600 * 24 * 7,  # 7 days
    # Worker configuration
    worker_prefetch_multiplier=1,
    worker_concurrency=4,
    # Task routing and priority
    task_routes={
        "app.tasks.backtest_tasks.run_backtest_task": {"queue": "backtest"},
        "app.tasks.backtest_tasks.run_monte_carlo_task": {"queue": "robustness"},
        "app.tasks.backtest_tasks.run_walk_forward_task": {"queue": "robustness"},
        "app.tasks.backtest_tasks.run_overfitting_task": {"queue": "robustness"},
        "app.tasks.backtest_tasks.run_optimizer_task": {"queue": "optimizer"},
        "app.tasks.backtest_tasks.run_walk_forward_opt_task": {"queue": "optimizer"},
    },
    task_default_priority=5,
    task_queue_max_priority=10,
    # Beat schedule for cleanup
    beat_schedule={
        "cleanup-old-results": {
            "task": "app.tasks.backtest_tasks.cleanup_old_results",
            "schedule": 3600 * 24,  # daily
        },
    },
)
