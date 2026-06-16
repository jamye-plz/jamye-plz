"""User model — OAuth provider accounts."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("provider", "provider_id", name="uq_users_provider_provider_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    provider: Mapped[str] = mapped_column(String(16))  # kakao | google
    provider_id: Mapped[str] = mapped_column(String(128))
    nickname: Mapped[str] = mapped_column(String(64))
    avatar_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # relationships
    memberships: Mapped[list["Membership"]] = relationship(  # noqa: F821
        "Membership", back_populates="user", lazy="noload"
    )
    owned_groups: Mapped[list["Group"]] = relationship(  # noqa: F821
        "Group", back_populates="owner", lazy="noload"
    )
    topics: Mapped[list["Topic"]] = relationship(  # noqa: F821
        "Topic", back_populates="author", lazy="noload"
    )
    messages: Mapped[list["Message"]] = relationship(  # noqa: F821
        "Message", back_populates="sender", lazy="noload"
    )
    push_subscriptions: Mapped[list["PushSubscription"]] = relationship(  # noqa: F821
        "PushSubscription", back_populates="user", lazy="noload"
    )
    notifications: Mapped[list["Notification"]] = relationship(  # noqa: F821
        "Notification", back_populates="user", lazy="noload"
    )
