"""Chat / message schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    chatroom_id: str
    sender_id: str | None = None
    client_msg_id: str | None = None
    body: str
    type: str
    created_at: datetime


class MessagePage(BaseModel):
    items: list[MessageOut]
    next_cursor: str | None = None


class ChatroomOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    group_id: str
    type: str
    topic_id: str | None = None
    created_at: datetime
