"""Topic model — the core jamye (jam-session topic)."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


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
    group: Mapped["Group"] = relationship(  # noqa: F821
        "Group", back_populates="topics", lazy="noload"
    )
    author: Mapped["User"] = relationship(  # noqa: F821
        "User", back_populates="topics", lazy="noload"
    )
    media: Mapped[list["TopicMedia"]] = relationship(  # noqa: F821
        "TopicMedia", back_populates="topic", lazy="noload", cascade="all, delete-orphan"
    )
    tags: Mapped[list["TopicTag"]] = relationship(  # noqa: F821
        "TopicTag", back_populates="topic", lazy="noload", cascade="all, delete-orphan"
    )
    chatroom: Mapped["Chatroom | None"] = relationship(  # noqa: F821
        "Chatroom", back_populates="topic", lazy="noload", uselist=False
    )
