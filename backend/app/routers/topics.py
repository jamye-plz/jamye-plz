"""Topics router — topic CRUD within a group."""

from fastapi import APIRouter, Query

from app.core.deps import CurrentUser, DbSession
from app.schemas.topic import TopicCreate, TopicOut, TopicPage, TopicPatch
from app.services.group_service import GroupService
from app.services.topic_service import TopicService

router = APIRouter(prefix="/groups/{group_id}/topics", tags=["topics"])


@router.post("", response_model=TopicOut, status_code=201)
async def create_topic(
    group_id: str,
    body: TopicCreate,
    current_user: CurrentUser,
    db: DbSession,
):
    group_svc = GroupService(db)
    await group_svc.require_membership(group_id, current_user.id)
    topic_svc = TopicService(db)
    return await topic_svc.create_topic(
        group_id=group_id, author_id=current_user.id, title=body.title
    )


@router.get("", response_model=TopicPage)
async def list_topics(
    group_id: str,
    current_user: CurrentUser,
    db: DbSession,
    cursor: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
):
    group_svc = GroupService(db)
    await group_svc.require_membership(group_id, current_user.id)
    topic_svc = TopicService(db)
    items, next_cursor = await topic_svc.list_topics(group_id, cursor=cursor, limit=limit)
    return TopicPage(items=items, next_cursor=next_cursor)


@router.get("/{topic_id}", response_model=TopicOut)
async def get_topic(
    group_id: str,
    topic_id: str,
    current_user: CurrentUser,
    db: DbSession,
):
    group_svc = GroupService(db)
    await group_svc.require_membership(group_id, current_user.id)
    topic_svc = TopicService(db)
    return await topic_svc.get_topic_or_404(topic_id)


@router.patch("/{topic_id}", response_model=TopicOut)
async def patch_topic(
    group_id: str,
    topic_id: str,
    body: TopicPatch,
    current_user: CurrentUser,
    db: DbSession,
):
    group_svc = GroupService(db)
    await group_svc.require_membership(group_id, current_user.id)
    topic_svc = TopicService(db)
    return await topic_svc.update_topic(
        topic_id=topic_id, user_id=current_user.id, body=body.body
    )
