"""ChatroomReadRepository — per-user-per-chatroom read receipts."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chatroom_read import ChatroomRead


class ChatroomReadRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get(self, user_id: str, chatroom_id: str) -> ChatroomRead | None:
        result = await self._db.execute(
            select(ChatroomRead).where(
                ChatroomRead.user_id == user_id,
                ChatroomRead.chatroom_id == chatroom_id,
            )
        )
        return result.scalar_one_or_none()

    async def upsert(
        self, user_id: str, chatroom_id: str, last_read_at: datetime
    ) -> ChatroomRead:
        """Find-or-create then update last_read_at."""
        existing = await self.get(user_id, chatroom_id)
        if existing:
            existing.last_read_at = last_read_at
            self._db.add(existing)
            await self._db.flush()
            await self._db.refresh(existing)
            return existing
        record = ChatroomRead(
            user_id=user_id,
            chatroom_id=chatroom_id,
            last_read_at=last_read_at,
        )
        self._db.add(record)
        await self._db.flush()
        await self._db.refresh(record)
        return record

    async def get_last_read_map(
        self, user_id: str, chatroom_ids: list[str]
    ) -> dict[str, datetime]:
        """Return {chatroom_id: last_read_at} for the given user and chatroom ids.

        One query using WHERE chatroom_id IN (...).
        """
        if not chatroom_ids:
            return {}
        result = await self._db.execute(
            select(ChatroomRead.chatroom_id, ChatroomRead.last_read_at).where(
                ChatroomRead.user_id == user_id,
                ChatroomRead.chatroom_id.in_(chatroom_ids),
            )
        )
        return {row.chatroom_id: row.last_read_at for row in result.all()}
