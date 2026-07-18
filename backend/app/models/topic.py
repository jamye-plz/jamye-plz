"""Topic model — the core jamye (jam-session topic)."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.chatroom import Chatroom
    from app.models.group import Group
    from app.models.topic_media import TopicMedia
    from app.models.topic_tag import TopicTag
    from app.models.user import User


class Topic(Base):
    __tablename__ = "topics"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    group_id: Mapped[str] = mapped_column(String(36), ForeignKey("groups.id"))
    author_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(256))
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="seed")  # seed | enriched
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # relationships
    group: Mapped["Group"] = relationship("Group", back_populates="topics", lazy="noload")
    author: Mapped["User"] = relationship("User", back_populates="topics", lazy="noload")
    media: Mapped[list["TopicMedia"]] = relationship(
        "TopicMedia", back_populates="topic", lazy="noload", cascade="all, delete-orphan"
    )
    tags: Mapped[list["TopicTag"]] = relationship(
        "TopicTag", back_populates="topic", lazy="noload", cascade="all, delete-orphan"
    )
    chatroom: Mapped["Chatroom | None"] = relationship(
        "Chatroom", back_populates="topic", lazy="noload", uselist=False
    )
