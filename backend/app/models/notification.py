"""Notification model — in-app notifications (read/unread)."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Index, JSON, DateTime, ForeignKey, String, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        # Partial unique index on (user_id, dedup_key) — only when dedup_key IS NOT NULL.
        # Allows multiple notifications without a dedup_key per user (e.g. system alerts)
        # while enforcing at most one live notification per (user, dedup_key) pair.
        Index(
            "ix_notifications_user_dedup",
            "user_id",
            "dedup_key",
            unique=True,
            postgresql_where=text("dedup_key IS NOT NULL"),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    type: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    dedup_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # relationships
    user: Mapped["User"] = relationship(  # noqa: F821
        "User", back_populates="notifications", lazy="noload"
    )
