"""MessageRepository — CRUD for Message model with idempotency support."""

from datetime import datetime

from sqlalchemy import func, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.message import Message


class MessageRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_id(self, message_id: str) -> Message | None:
        result = await self._db.execute(select(Message).where(Message.id == message_id))
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

    async def latest_created_at_by_chatrooms(
        self, chatroom_ids: list[str]
    ) -> dict[str, datetime]:
        """Return {chatroom_id: max(created_at)} for the given chatroom ids.

        One query using GROUP BY chatroom_id — no N+1.
        """
        if not chatroom_ids:
            return {}
        result = await self._db.execute(
            select(Message.chatroom_id, func.max(Message.created_at).label("max_created_at"))
            .where(Message.chatroom_id.in_(chatroom_ids))
            .group_by(Message.chatroom_id)
        )
        return {row.chatroom_id: row.max_created_at for row in result.all()}

    async def list_by_chatroom(
        self,
        chatroom_id: str,
        cursor: str | None = None,
        limit: int = 50,
    ) -> tuple[list[Message], str | None]:
        # Keyset pagination on (created_at, id): the cursor filter must use the
        # same key as ORDER BY, otherwise random UUID ids skip/duplicate rows.
        query = (
            select(Message)
            .where(Message.chatroom_id == chatroom_id)
            .order_by(Message.created_at.desc(), Message.id.desc())
        )
        if cursor:
            cur_created, cur_id = cursor.split("|", 1)
            query = query.where(
                tuple_(Message.created_at, Message.id)
                < tuple_(datetime.fromisoformat(cur_created), cur_id)
            )
        query = query.limit(limit + 1)
        result = await self._db.execute(query)
        rows = list(result.scalars().all())
        next_cursor: str | None = None
        if len(rows) > limit:
            rows = rows[:limit]
            last = rows[-1]
            next_cursor = f"{last.created_at.isoformat()}|{last.id}"
        return rows, next_cursor
