"""Group model — closed groups accessed by invite only."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.chatroom import Chatroom
    from app.models.invite import Invite
    from app.models.membership import Membership
    from app.models.topic import Topic
    from app.models.user import User


class Group(Base):
    __tablename__ = "groups"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(128))
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    max_members: Mapped[int] = mapped_column(Integer, default=12)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # relationships
    owner: Mapped["User"] = relationship("User", back_populates="owned_groups", lazy="noload")
    memberships: Mapped[list["Membership"]] = relationship(
        "Membership", back_populates="group", lazy="noload"
    )
    invites: Mapped[list["Invite"]] = relationship("Invite", back_populates="group", lazy="noload")
    topics: Mapped[list["Topic"]] = relationship("Topic", back_populates="group", lazy="noload")
    chatrooms: Mapped[list["Chatroom"]] = relationship(
        "Chatroom", back_populates="group", lazy="noload"
    )
