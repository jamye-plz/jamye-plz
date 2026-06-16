"""MessageRepository — CRUD for Message model with idempotency support."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.message import Message


class MessageRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_id(self, message_id: str) -> Message | None:
        result = await self._db.execute(
            select(Message).where(Message.id == message_id)
        )
        return result.scalar_one_or_none()

    async def get_by_client_msg_id(self, sender_id: str, client_msg_id: str) -> Message | None:
        """Lookup by idempotency key — returns existing message on retry."""
        result = await self._db.execute(
            select(Message).where(
                Message.sender_id == sender_id,
                Message.client_msg_id == client_msg_id,
            )
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        chatroom_id: str,
        body: str,
        sender_id: str | None = None,
        client_msg_id: str | None = None,
        type: str = "user",
    ) -> Message:
        message = Message(
            chatroom_id=chatroom_id,
            sender_id=sender_id,
            client_msg_id=client_msg_id,
            body=body,
            type=type,
        )
        self._db.add(message)
        await self._db.flush()
        await self._db.refresh(message)
        return message

    async def list_by_chatroom(
        self,
        chatroom_id: str,
        cursor: str | None = None,
        limit: int = 50,
    ) -> tuple[list[Message], str | None]:
        query = (
            select(Message)
            .where(Message.chatroom_id == chatroom_id)
            .order_by(Message.created_at.desc())
        )
        if cursor:
            query = query.where(Message.id < cursor)
        query = query.limit(limit + 1)
        result = await self._db.execute(query)
        rows = list(result.scalars().all())
        next_cursor: str | None = None
        if len(rows) > limit:
            next_cursor = rows[limit - 1].id
            rows = rows[:limit]
        return rows, next_cursor
