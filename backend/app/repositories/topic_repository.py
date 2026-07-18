"""TopicRepository — CRUD for Topic, TopicMedia, TopicTag models."""

from datetime import datetime

from sqlalchemy import func, literal, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.timeutil import seoul_day_window
from app.models.chatroom import Chatroom
from app.models.topic import Topic
from app.models.topic_media import TopicMedia
from app.models.topic_tag import TopicTag


class TopicRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_id(self, topic_id: str) -> Topic | None:
        result = await self._db.execute(select(Topic).where(Topic.id == topic_id))
        return result.scalar_one_or_none()

    async def create(self, group_id: str, author_id: str, title: str) -> Topic:
        topic = Topic(group_id=group_id, author_id=author_id, title=title)
        self._db.add(topic)
        await self._db.flush()
        await self._db.refresh(topic)
        return topic

    async def update(
        self, topic: Topic, body: str | None = None, status: str | None = None
    ) -> Topic:
        if body is not None:
            topic.body = body
        if status is not None:
            topic.status = status
        self._db.add(topic)
        await self._db.flush()
        await self._db.refresh(topic)
        return topic

    async def list_by_group(
        self,
        group_id: str,
        cursor: str | None = None,
        limit: int = 20,
        date: str | None = None,
    ) -> tuple[list[Topic], str | None]:
        """Keyset-paginated topic list, optionally filtered to a calendar date.

        When `date` ("YYYY-MM-DD") is given, results are constrained to the
        Asia/Seoul calendar day boundary (converted to UTC).
        """
        query = (
            select(Topic)
            .where(Topic.group_id == group_id)
            .order_by(Topic.created_at.desc(), Topic.id.desc())
        )
        if date:
            start_utc, end_utc = seoul_day_window(date)
            query = query.where(
                Topic.created_at >= start_utc,
                Topic.created_at < end_utc,
            )
        if cursor:
            cur_created, cur_id = cursor.split("|", 1)
            query = query.where(
                tuple_(Topic.created_at, Topic.id)
                < tuple_(literal(datetime.fromisoformat(cur_created)), literal(cur_id))
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

    async def distinct_dates(self, group_id: str, tz_name: str = "Asia/Seoul") -> list[str]:
        """Return distinct calendar dates (in tz_name) that have topics, descending.

        Uses Postgres: func.date(func.timezone(tz_name, created_at)) to localise
        the stored timestamptz before extracting the date.
        """
        local_date = func.date(func.timezone(tz_name, Topic.created_at)).label("d")
        result = await self._db.execute(
            select(local_date)
            .where(Topic.group_id == group_id)
            .distinct()
            .order_by(local_date.desc())
        )
        return [str(row.d) for row in result.all()]

    async def topic_chatroom_map(self, topic_ids: list[str]) -> dict[str, str]:
        """Return {topic_id: chatroom_id} for the given topic ids.

        One query — avoids N+1 in unread computation.
        """
        if not topic_ids:
            return {}
        result = await self._db.execute(
            select(Chatroom.topic_id, Chatroom.id).where(
                Chatroom.topic_id.in_(topic_ids),
                Chatroom.type == "topic",
            )
        )
        return {row.topic_id: row.id for row in result.all()}


class TopicMediaRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(
        self,
        topic_id: str,
        type: str,
        object_key: str,
        width: int | None = None,
        height: int | None = None,
        byte_size: int | None = None,
    ) -> TopicMedia:
        media = TopicMedia(
            topic_id=topic_id,
            type=type,
            object_key=object_key,
            width=width,
            height=height,
            byte_size=byte_size,
        )
        self._db.add(media)
        await self._db.flush()
        await self._db.refresh(media)
        return media

    async def list_by_topic(self, topic_id: str) -> list[TopicMedia]:
        result = await self._db.execute(select(TopicMedia).where(TopicMedia.topic_id == topic_id))
        return list(result.scalars().all())


class TopicTagRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def delete_by_topic(self, topic_id: str) -> None:
        result = await self._db.execute(select(TopicTag).where(TopicTag.topic_id == topic_id))
        for tag in result.scalars().all():
            await self._db.delete(tag)
        await self._db.flush()

    async def bulk_create(self, topic_id: str, tags: list[dict]) -> list[TopicTag]:
        created: list[TopicTag] = []
        for tag_data in tags:
            tag = TopicTag(
                topic_id=topic_id,
                tag=tag_data["tag"],
                source=tag_data["source"],
                confidence=tag_data.get("confidence"),
            )
            self._db.add(tag)
            created.append(tag)
        await self._db.flush()
        for tag in created:
            await self._db.refresh(tag)
        return created

    async def list_by_topic(self, topic_id: str) -> list[TopicTag]:
        result = await self._db.execute(select(TopicTag).where(TopicTag.topic_id == topic_id))
        return list(result.scalars().all())
