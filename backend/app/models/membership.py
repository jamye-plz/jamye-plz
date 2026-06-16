"""Membership model — N:M between users and groups with role."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (
        UniqueConstraint("group_id", "user_id", name="uq_memberships_group_user"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    group_id: Mapped[str] = mapped_column(String(36), ForeignKey("groups.id"))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    role: Mapped[str] = mapped_column(String(16))  # owner | member
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # relationships
    group: Mapped["Group"] = relationship(  # noqa: F821
        "Group", back_populates="memberships", lazy="noload"
    )
    user: Mapped["User"] = relationship(  # noqa: F821
        "User", back_populates="memberships", lazy="noload"
    )
