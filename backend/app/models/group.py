"""Group model — closed groups accessed by invite only."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Group(Base):
    __tablename__ = "groups"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(128))
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    max_members: Mapped[int] = mapped_column(Integer, default=12)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # relationships
    owner: Mapped["User"] = relationship(  # noqa: F821
        "User", back_populates="owned_groups", lazy="noload"
    )
    memberships: Mapped[list["Membership"]] = relationship(  # noqa: F821
        "Membership", back_populates="group", lazy="noload"
    )
    invites: Mapped[list["Invite"]] = relationship(  # noqa: F821
        "Invite", back_populates="group", lazy="noload"
    )
    topics: Mapped[list["Topic"]] = relationship(  # noqa: F821
        "Topic", back_populates="group", lazy="noload"
    )
    chatrooms: Mapped[list["Chatroom"]] = relationship(  # noqa: F821
        "Chatroom", back_populates="group", lazy="noload"
    )
