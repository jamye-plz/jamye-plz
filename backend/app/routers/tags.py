"""Tags router — topic tag sync."""

from fastapi import APIRouter

from app.core.deps import CurrentUser, DbSession
from app.schemas.topic import TagOut, TagsSync
from app.services.group_service import GroupService
from app.services.topic_service import TopicService

router = APIRouter(prefix="/groups/{group_id}/topics/{topic_id}/tags", tags=["tags"])


@router.put("", response_model=list[TagOut])
async def sync_tags(
    group_id: str,
    topic_id: str,
    body: TagsSync,
    current_user: CurrentUser,
    db: DbSession,
):
    group_svc = GroupService(db)
    await group_svc.require_membership(group_id, current_user.id)
    topic_svc = TopicService(db)
    await topic_svc.get_topic_or_404(topic_id)
    return await topic_svc.sync_tags(topic_id, body.tags)


@router.get("", response_model=list[TagOut])
async def list_tags(
    group_id: str,
    topic_id: str,
    current_user: CurrentUser,
    db: DbSession,
):
    group_svc = GroupService(db)
    await group_svc.require_membership(group_id, current_user.id)
    topic_svc = TopicService(db)
    return await topic_svc.list_tags(topic_id)
