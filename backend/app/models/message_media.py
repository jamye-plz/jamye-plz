"""MessageMedia model — photos/video attached to a chat message.

Message-scoped mirror of TopicMedia. Unlike topic media there is no confirm
step: `message_id` is a FK, so a row cannot exist before its message. The
upload metadata rides the WS `send_message` frame and both rows are written in
one transaction (see ChatService.send_message).
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.message import Message


class MessageMedia(Base):
    __tablename__ = "message_media"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    message_id: Mapped[str] = mapped_column(String(36), ForeignKey("messages.id"), index=True)
    # content_type (e.g. "image/jpeg", "video/mp4"). Named `type` to mirror
    # topic_media; widened to 64 so a longer MIME can never truncate.
    type: Mapped[str] = mapped_column(String(64))
    object_key: Mapped[str] = mapped_column(String(512))
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    byte_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Seconds. Video only; null for images.
    duration: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Order within the message. created_at is identical across a message's
    # attachments (one transaction, stable now()), so without this the ordering
    # tiebreak is a random uuid and reloaded history reshuffles the set.
    position: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # relationships
    message: Mapped["Message"] = relationship("Message", back_populates="media", lazy="noload")
