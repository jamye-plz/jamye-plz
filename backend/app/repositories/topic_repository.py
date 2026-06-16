"""TopicRepository — CRUD for Topic, TopicMedia, TopicTag models."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.topic import Topic
from app.models.topic_media import TopicMedia
from app.models.topic_tag import TopicTag


class TopicRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_id(self, topic_id: str) -> Topic | None:
        result = await self._db.execute(
            select(Topic).where(Topic.id == topic_id)
        )
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
    ) -> tuple[list[Topic], str | None]:
        query = select(Topic).where(Topic.group_id == group_id).order_by(Topic.created_at.desc())
        if cursor:
            query = query.where(Topic.id < cursor)
        query = query.limit(limit + 1)
        result = await self._db.execute(query)
        rows = list(result.scalars().all())
        next_cursor: str | None = None
        if len(rows) > limit:
            next_cursor = rows[limit - 1].id
            rows = rows[:limit]
        return rows, next_cursor


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
        result = await self._db.execute(
            select(TopicMedia).where(TopicMedia.topic_id == topic_id)
        )
        return list(result.scalars().all())


class TopicTagRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def delete_by_topic(self, topic_id: str) -> None:
        result = await self._db.execute(
            select(TopicTag).where(TopicTag.topic_id == topic_id)
        )
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
        result = await self._db.execute(
            select(TopicTag).where(TopicTag.topic_id == topic_id)
        )
        return list(result.scalars().all())
