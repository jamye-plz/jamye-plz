"""Chatrooms router — chatroom listing, message history, and read receipts."""

from fastapi import APIRouter, Query, Response

from app.core.deps import CurrentUser, DbSession
from app.schemas.chat import ChatroomOut, MessagePage
from app.services.chat_service import ChatService
from app.services.group_service import GroupService

router = APIRouter(prefix="/groups/{group_id}/chatrooms", tags=["chatrooms"])


@router.get("", response_model=list[ChatroomOut])
async def list_chatrooms(group_id: str, current_user: CurrentUser, db: DbSession):
    group_svc = GroupService(db)
    await group_svc.require_membership(group_id, current_user.id)
    chat_svc = ChatService(db)
    return await chat_svc.list_group_chatrooms(group_id)


@router.get("/{chatroom_id}/messages", response_model=MessagePage)
async def list_messages(
    group_id: str,
    chatroom_id: str,
    current_user: CurrentUser,
    db: DbSession,
    cursor: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    group_svc = GroupService(db)
    await group_svc.require_membership(group_id, current_user.id)
    chat_svc = ChatService(db)
    await chat_svc.get_chatroom_in_group_or_404(chatroom_id, group_id)
    items, next_cursor = await chat_svc.list_messages_out(chatroom_id, cursor=cursor, limit=limit)
    return MessagePage(items=items, next_cursor=next_cursor)


@router.post("/{chatroom_id}/read", status_code=204)
async def mark_chatroom_read(
    group_id: str,
    chatroom_id: str,
    current_user: CurrentUser,
    db: DbSession,
):
    """Mark the chatroom as read for the current user.

    Verifies membership and that the chatroom belongs to the group,
    then upserts a ChatroomRead record. If the chatroom is a topic chatroom,
    also clears chat_unread and new_topic notifications for this user.
    """
    group_svc = GroupService(db)
    await group_svc.require_membership(group_id, current_user.id)
    chat_svc = ChatService(db)
    # Verify chatroom belongs to group (IDOR guard)
    await chat_svc.get_chatroom_in_group_or_404(chatroom_id, group_id)
    await chat_svc.mark_read(chatroom_id=chatroom_id, user_id=current_user.id)
    return Response(status_code=204)
