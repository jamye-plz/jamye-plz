"""Topics router — topic CRUD within a group."""

from datetime import datetime, timezone

from fastapi import APIRouter, Query

from app.core import ws_hub
from app.core.deps import CurrentUser, DbSession
from app.repositories.chatroom_read_repository import ChatroomReadRepository
from app.repositories.group_repository import ChatroomRepository
from app.schemas.topic import TopicCreate, TopicDatesOut, TopicOut, TopicPage, TopicPatch
from app.services.chat_service import ChatService
from app.services.group_service import GroupService
from app.services.notification_service import NotificationService
from app.services.push_dispatch import schedule_push_dispatch
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
    recipient_ids: list[str] = []
    for member in await group_svc.list_members(group_id):
        if member.user_id != current_user.id:
            recipient_ids.append(member.user_id)
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
                dedup_key=f"new_topic:{topic.id}",
            )

    # Web Push (M1): fire-and-forget, never blocks the response.
    schedule_push_dispatch(
        recipient_ids,
        {
            "title": f"{group.name} 새 주제",
            "body": topic.title,
            "url": chat_path,
        },
    )

    # Mark the author's own topic chatroom as read at creation so the author's
    # own new topic is not shown as unread.
    chatroom_repo = ChatroomRepository(db)
    topic_chatroom = await chatroom_repo.get_by_topic(topic.id)
    if topic_chatroom:
        chatroom_read_repo = ChatroomReadRepository(db)
        await chatroom_read_repo.upsert(
            user_id=current_user.id,
            chatroom_id=topic_chatroom.id,
            last_read_at=datetime.now(timezone.utc),
        )
        await db.commit()

    return await topic_svc.to_topic_out(topic)


# NOTE: /dates must be declared BEFORE /{topic_id} to prevent "dates" being
# captured as a topic_id path parameter.
@router.get("/dates", response_model=TopicDatesOut)
async def list_topic_dates(
    group_id: str,
    current_user: CurrentUser,
    db: DbSession,
):
    group_svc = GroupService(db)
    await group_svc.require_membership(group_id, current_user.id)
    topic_svc = TopicService(db)
    return await topic_svc.list_topic_dates(group_id)


@router.get("", response_model=TopicPage)
async def list_topics(
    group_id: str,
    current_user: CurrentUser,
    db: DbSession,
    cursor: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    date: str | None = Query(None),
):
    group_svc = GroupService(db)
    await group_svc.require_membership(group_id, current_user.id)
    topic_svc = TopicService(db)
    items, next_cursor = await topic_svc.list_topics(
        group_id, cursor=cursor, limit=limit, date=date
    )
    # Compute unread map for the whole page in 3 queries (no N+1).
    unread_map = await topic_svc.compute_unread_map(items, current_user.id)
    out_items = [await topic_svc.to_topic_out(t, unread=unread_map.get(t.id, False)) for t in items]
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
