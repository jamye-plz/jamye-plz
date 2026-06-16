"""TopicService — topic CRUD and tag/media management."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, NotFoundError
from app.models.topic import Topic
from app.models.topic_media import TopicMedia
from app.models.topic_tag import TopicTag
from app.repositories.group_repository import MembershipRepository
from app.repositories.topic_repository import (
    TopicMediaRepository,
    TopicRepository,
    TopicTagRepository,
)
from app.schemas.topic import TagItem


class TopicService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._topic_repo = TopicRepository(db)
        self._media_repo = TopicMediaRepository(db)
        self._tag_repo = TopicTagRepository(db)
        self._membership_repo = MembershipRepository(db)

    async def create_topic(self, group_id: str, author_id: str, title: str) -> Topic:
        topic = await self._topic_repo.create(
            group_id=group_id, author_id=author_id, title=title
        )
        await self._db.commit()
        await self._db.refresh(topic)
        return topic

    async def get_topic_or_404(self, topic_id: str) -> Topic:
        topic = await self._topic_repo.get_by_id(topic_id)
        if topic is None:
            raise NotFoundError("Topic", topic_id)
        return topic

    async def list_topics(
        self, group_id: str, cursor: str | None = None, limit: int = 20
    ) -> tuple[list[Topic], str | None]:
        return await self._topic_repo.list_by_group(group_id, cursor=cursor, limit=limit)

    async def update_topic(
        self,
        topic_id: str,
        user_id: str,
        body: str | None = None,
        status: str | None = None,
    ) -> Topic:
        topic = await self.get_topic_or_404(topic_id)
        # Only author or group owner may edit
        if topic.author_id != user_id:
            membership = await self._membership_repo.get(topic.group_id, user_id)
            if membership is None or membership.role != "owner":
                raise ForbiddenError("Only the author or group owner can edit this topic")
        topic = await self._topic_repo.update(topic, body=body, status=status)
        await self._db.commit()
        await self._db.refresh(topic)
        return topic

    async def sync_tags(self, topic_id: str, tags: list[TagItem]) -> list[TopicTag]:
        await self._tag_repo.delete_by_topic(topic_id)
        tag_dicts = [t.model_dump() for t in tags]
        created = await self._tag_repo.bulk_create(topic_id, tag_dicts)
        await self._db.commit()
        return created

    async def list_tags(self, topic_id: str) -> list[TopicTag]:
        return await self._tag_repo.list_by_topic(topic_id)

    async def confirm_media(
        self,
        topic_id: str,
        object_key: str,
        content_type: str,
        width: int | None = None,
        height: int | None = None,
        byte_size: int | None = None,
    ) -> TopicMedia:
        media = await self._media_repo.create(
            topic_id=topic_id,
            type=content_type,
            object_key=object_key,
            width=width,
            height=height,
            byte_size=byte_size,
        )
        await self._db.commit()
        await self._db.refresh(media)
        return media

    async def list_media(self, topic_id: str) -> list[TopicMedia]:
        return await self._media_repo.list_by_topic(topic_id)
