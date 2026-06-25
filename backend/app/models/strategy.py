import uuid
from datetime import datetime, timezone
from enum import Enum as PyEnum
from typing import List, Optional

from sqlalchemy import DateTime, ForeignKey, String, func, Index
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class StrategyStatus(str, PyEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class Strategy(Base):
    __tablename__ = "strategies"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(
        String(1000), nullable=True
    )
    # Intermediate representation (JSON) for strategy rules / parameters
    ir_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    # Additional configuration for strategy runtime
    config: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    status: Mapped[StrategyStatus] = mapped_column(
        String(20), default=StrategyStatus.DRAFT, nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user: Mapped["User"] = relationship("User", back_populates="strategies")
    backtests: Mapped[List["Backtest"]] = relationship(
        "Backtest", back_populates="strategy", cascade="all, delete-orphan",
        lazy="selectin"
    )

    __table_args__ = (
        Index("ix_strategies_user_id_status", "user_id", "status"),
    )
