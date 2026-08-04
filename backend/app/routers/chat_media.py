"""Chat media router — presign uploads for chat message attachments.

Only presign lives here. There is deliberately no confirm endpoint: a
message_media row needs a message_id, so the attachment metadata rides the WS
`send_message` frame instead and both rows are written together (see
ChatService.send_message and docs/architecture/api-contract.md flow 3).
"""

import uuid

from fastapi import APIRouter
from fastapi.responses import RedirectResponse

from app.core import storage
from app.core.deps import CurrentUser, DbSession
from app.schemas.chat import ChatMediaPresignOut, ChatMediaPresignRequest
from app.services.chat_service import ChatService
from app.services.group_service import GroupService

router = APIRouter(prefix="/groups/{group_id}/chatrooms/{chatroom_id}/media", tags=["chat-media"])


@router.post("/presign", response_model=ChatMediaPresignOut)
async def presign_chat_media(
    group_id: str,
    chatroom_id: str,
    body: ChatMediaPresignRequest,
    current_user: CurrentUser,
    db: DbSession,
):
    # Same two-step gate the rest of the chatrooms router uses: membership in
    # the group, then confirm the chatroom actually belongs to it (IDOR guard).
    group_svc = GroupService(db)
    await group_svc.require_membership(group_id, current_user.id)
    chat_svc = ChatService(db)
    await chat_svc.get_chatroom_in_group_or_404(chatroom_id, group_id)

    # Key shape is load-bearing: ChatService.validate_object_key_for_chatroom
    # rejects anything not matching `chat/{chatroom_id}/{single-segment}`.
    object_key = f"chat/{chatroom_id}/{uuid.uuid4()}"
    upload_url, expires_in = storage.presign_put(object_key, body.content_type, body.byte_size)
    return ChatMediaPresignOut(
        object_key=object_key,
        upload_url=upload_url,
        expires_in=expires_in,
    )


@router.get("/{media_id}/download")
async def download_chat_media(
    group_id: str,
    chatroom_id: str,
    media_id: str,
    current_user: CurrentUser,
    db: DbSession,
):
    """Redirect to a signed URL that forces a save.

    A redirect rather than a `download_url` field on every history item: the
    payload stays small, and authorization is re-checked at click time instead
    of being baked into a URL minted when the page loaded.
    """
    group_svc = GroupService(db)
    await group_svc.require_membership(group_id, current_user.id)
    chat_svc = ChatService(db)
    await chat_svc.get_chatroom_in_group_or_404(chatroom_id, group_id)
    url = await chat_svc.presign_media_download(chatroom_id, media_id)
    # 307 keeps the method and, unlike 301/302, is explicitly non-cacheable by
    # default — the target URL expires in minutes and must not be reused.
    return RedirectResponse(url, status_code=307)
