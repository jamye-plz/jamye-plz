"""ChatroomReadRepository — per-user-per-chatroom read receipts."""

import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
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

    async def upsert(self, user_id: str, chatroom_id: str, last_read_at: datetime) -> ChatroomRead:
        """Atomically record/refresh the read receipt.

        Uses Postgres ``INSERT ... ON CONFLICT DO UPDATE`` on the
        ``(user_id, chatroom_id)`` unique constraint so two concurrent first
        reads (same user, two tabs/devices) can't race into an IntegrityError
        that would 500 and leave the topic unread.
        """
        insert_stmt = pg_insert(ChatroomRead).values(
            id=str(uuid.uuid4()),
            user_id=user_id,
            chatroom_id=chatroom_id,
            last_read_at=last_read_at,
        )
        stmt = insert_stmt.on_conflict_do_update(
            constraint="uq_chatroom_reads_user_chatroom",
            # Keep the receipt monotonic: out-of-order reads (an earlier entry read
            # committing after a later live-message read) must not move
            # last_read_at backwards, which would resurface already-seen messages.
            set_={
                "last_read_at": func.greatest(
                    ChatroomRead.last_read_at, insert_stmt.excluded.last_read_at
                )
            },
        )
        await self._db.execute(stmt)
        await self._db.flush()
        record = await self.get(user_id, chatroom_id)
        assert record is not None  # row was just upserted within this transaction
        # Core ON CONFLICT bypasses the ORM unit of work; refresh to avoid stale
        # attributes on an already-identity-mapped row.
        await self._db.refresh(record)
        return record

    async def get_last_read_map(self, user_id: str, chatroom_ids: list[str]) -> dict[str, datetime]:
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
