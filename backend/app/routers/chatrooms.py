"""Chatrooms router — chatroom listing and message history."""

from fastapi import APIRouter, Query

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
