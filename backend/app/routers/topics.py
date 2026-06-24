"""Topics router — topic CRUD within a group."""

from fastapi import APIRouter, Query

from app.core import ws_hub
from app.core.deps import CurrentUser, DbSession
from app.schemas.topic import TopicCreate, TopicOut, TopicPage, TopicPatch
from app.services.chat_service import ChatService
from app.services.group_service import GroupService
from app.services.notification_service import NotificationService
from app.services.topic_service import TopicService

router = APIRouter(prefix="/groups/{group_id}/topics", tags=["topics"])


def _md_escape(text: str) -> str:
    """Escape markdown link-breaking metacharacters so a user-controlled topic
    title can't break out of the announcement's link text and hijack the href."""
    for ch in ("\\", "[", "]", "(", ")"):
        text = text.replace(ch, "\\" + ch)
    return text


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
    topic = await topic_svc.create_topic(
        group_id=group_id, author_id=current_user.id, title=body.title
    )

    # New-topic announcement (T11): the author posts a message into the group main
    # chat with an inline markdown link to the new topic's chatroom (rendered by
    # the client); also create in-app notifications.
    chat_svc = ChatService(db)
    main = await chat_svc.get_main_chatroom(group_id)
    chat_path = f"/groups/{group_id}/topics/{topic.id}/chat"
    announce = f"새로운 주제를 올렸어요: [{_md_escape(topic.title)}]({chat_path})"
    msg = await chat_svc.post_user_message(main.id, sender_id=current_user.id, body=announce)
    await ws_hub.broadcast(
        main.id,
        {
            "type": "message",
            "id": msg.id,
            "chatroom_id": main.id,
            "sender_id": current_user.id,
            "sender_nickname": current_user.nickname,
            "sender_avatar_url": current_user.avatar_url,
            "client_msg_id": None,
            "body": msg.body,
            "msg_type": msg.type,
            "created_at": msg.created_at.isoformat(),
        },
    )

    notif_svc = NotificationService(db)
    group = await group_svc.get_group_or_404(group_id)
    for member in await group_svc.list_members(group_id):
        if member.user_id != current_user.id:
            await notif_svc.create_notification(
                user_id=member.user_id,
                type="new_topic",
                payload={
                    "group_id": group_id,
                    "group_name": group.name,
                    "topic_id": topic.id,
                    "title": topic.title,
                    "author": current_user.nickname,
                },
            )

    return await topic_svc.to_topic_out(topic)


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
    out_items = [await topic_svc.to_topic_out(t) for t in items]
    return TopicPage(items=out_items, next_cursor=next_cursor)


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
    topic = await topic_svc.get_topic_in_group_or_404(topic_id, group_id)
    return await topic_svc.to_topic_out(topic)


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
    await topic_svc.get_topic_in_group_or_404(topic_id, group_id)
    # Enriching a seed topic with a body marks it enriched (API contract semantics).
    topic = await topic_svc.update_topic(
        topic_id=topic_id,
        user_id=current_user.id,
        body=body.body,
        status="enriched" if body.body is not None else None,
    )
    return await topic_svc.to_topic_out(topic)
