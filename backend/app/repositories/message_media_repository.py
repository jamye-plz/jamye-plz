"""MessageMediaRepository — attachments for chat messages."""

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.message_media import MessageMedia


class MessageMediaRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create_many(
        self,
        message_id: str,
        items: Sequence[dict[str, object]],
    ) -> list[MessageMedia]:
        """Attach media rows to a message.

        Does NOT commit — the caller owns the transaction so the message and
        its media are written as one unit.
        """
        rows = [
            MessageMedia(
                message_id=message_id,
                type=item["content_type"],
                object_key=item["object_key"],
                width=item.get("width"),
                height=item.get("height"),
                byte_size=item.get("byte_size"),
                duration=item.get("duration"),
            )
            for item in items
        ]
        self._db.add_all(rows)
        await self._db.flush()
        return rows

    async def list_by_message_ids(self, message_ids: Sequence[str]) -> list[MessageMedia]:
        """Batch-load media for a page of messages.

        One query for the whole page — history rendering must not issue a
        query per message.
        """
        if not message_ids:
            return []
        result = await self._db.execute(
            select(MessageMedia)
            .where(MessageMedia.message_id.in_(message_ids))
            .order_by(MessageMedia.created_at, MessageMedia.id)
        )
        return list(result.scalars().all())

    async def list_by_message(self, message_id: str) -> list[MessageMedia]:
        result = await self._db.execute(
            select(MessageMedia)
            .where(MessageMedia.message_id == message_id)
            .order_by(MessageMedia.created_at, MessageMedia.id)
        )
        return list(result.scalars().all())
