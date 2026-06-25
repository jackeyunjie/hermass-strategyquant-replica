import uuid
from datetime import datetime, timezone
from enum import Enum as PyEnum
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, func, Index
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class BacktestStatus(str, PyEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Backtest(Base):
    __tablename__ = "backtests"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    strategy_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("strategies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[BacktestStatus] = mapped_column(
        String(20), default=BacktestStatus.PENDING, nullable=False, index=True
    )
    # Configuration used for this backtest
    config: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    # Raw engine output: equity_curve, trades, etc.
    result: Mapped[Optional[dict]] = mapped_column(
        JSONB, nullable=True, doc="Equity curve, trades list, etc."
    )
    # Aggregated metrics: Sharpe, max drawdown, CAGR, etc.
    metrics: Mapped[Optional[dict]] = mapped_column(
        JSONB, nullable=True, doc="Performance metrics summary"
    )
    # Error message if backtest failed
    error_message: Mapped[Optional[str]] = mapped_column(
        String(2000), nullable=True
    )
    # Celery task ID for tracking
    task_id: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, index=True
    )
    # Runtime duration in seconds
    runtime_seconds: Mapped[Optional[float]] = mapped_column(
        nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    strategy: Mapped["Strategy"] = relationship(
        "Strategy", back_populates="backtests"
    )

    __table_args__ = (
        Index("ix_backtests_strategy_id_status", "strategy_id", "status"),
    )
