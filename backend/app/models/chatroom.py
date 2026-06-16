"""Chatroom model — main (one per group) and topic chatrooms."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Chatroom(Base):
    __tablename__ = "chatrooms"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    group_id: Mapped[str] = mapped_column(String(36), ForeignKey("groups.id"))
    type: Mapped[str] = mapped_column(String(8))  # main | topic
    topic_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("topics.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # relationships
    group: Mapped["Group"] = relationship(  # noqa: F821
        "Group", back_populates="chatrooms", lazy="noload"
    )
    topic: Mapped["Topic | None"] = relationship(  # noqa: F821
        "Topic", back_populates="chatroom", lazy="noload"
    )
    messages: Mapped[list["Message"]] = relationship(  # noqa: F821
        "Message", back_populates="chatroom", lazy="noload", cascade="all, delete-orphan"
    )
