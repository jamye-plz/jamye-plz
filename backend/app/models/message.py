"""Message model — user and system chat messages with idempotency key."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.chatroom import Chatroom
    from app.models.user import User


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        # Partial unique index: only enforce uniqueness when client_msg_id IS NOT NULL.
        # PostgreSQL treats NULL as distinct, so system messages (both NULL) are excluded
        # from the constraint naturally. We add an explicit partial index for clarity.
        Index(
            "ix_messages_sender_client_msg_id",
            "sender_id",
            "client_msg_id",
            unique=True,
            postgresql_where=text("client_msg_id IS NOT NULL"),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    chatroom_id: Mapped[str] = mapped_column(String(36), ForeignKey("chatrooms.id"))
    sender_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    client_msg_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    body: Mapped[str] = mapped_column(Text)
    type: Mapped[str] = mapped_column(String(8), default="user")  # user | system
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # relationships
    chatroom: Mapped["Chatroom"] = relationship(
        "Chatroom", back_populates="messages", lazy="noload"
    )
    sender: Mapped["User | None"] = relationship("User", back_populates="messages", lazy="noload")
