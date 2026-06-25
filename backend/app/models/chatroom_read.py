"""ChatroomRead model — per-user-per-chatroom read receipt."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ChatroomRead(Base):
    __tablename__ = "chatroom_reads"
    __table_args__ = (
        UniqueConstraint("user_id", "chatroom_id", name="uq_chatroom_reads_user_chatroom"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    chatroom_id: Mapped[str] = mapped_column(String(36), ForeignKey("chatrooms.id"))
    last_read_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
