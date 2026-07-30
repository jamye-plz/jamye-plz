"""Media router — presign and confirm media uploads.

Real presigned PUT URLs are generated only when MinIO/S3 keys are
provisioned (settings.minio_enabled); otherwise storage.presign_put returns
a deterministic local fallback URL so the demo works without an object
store. See app.core.storage for the env-conditional implementation.
"""

import uuid

from fastapi import APIRouter

from app.core import storage
from app.core.deps import CurrentUser, DbSession
from app.schemas.topic import MediaConfirmRequest, MediaOut, MediaPresignOut, MediaPresignRequest
from app.services.group_service import GroupService
from app.services.topic_service import TopicService

router = APIRouter(prefix="/groups/{group_id}/topics/{topic_id}/media", tags=["media"])


@router.post("/presign", response_model=MediaPresignOut)
async def presign_upload(
    group_id: str,
    topic_id: str,
    body: MediaPresignRequest,
    current_user: CurrentUser,
    db: DbSession,
):
    group_svc = GroupService(db)
    await group_svc.require_membership(group_id, current_user.id)
    topic_svc = TopicService(db)
    topic = await topic_svc.get_topic_in_group_or_404(topic_id, group_id)
    await topic_svc.assert_author_or_owner(topic, current_user.id)

    object_key = f"topics/{topic_id}/{uuid.uuid4()}"
    upload_url, expires_in = storage.presign_put(object_key, body.content_type, body.byte_size)
    return MediaPresignOut(
        object_key=object_key,
        upload_url=upload_url,
        expires_in=expires_in,
    )


@router.post("/confirm", response_model=MediaOut, status_code=201)
async def confirm_upload(
    group_id: str,
    topic_id: str,
    body: MediaConfirmRequest,
    current_user: CurrentUser,
    db: DbSession,
):
    group_svc = GroupService(db)
    await group_svc.require_membership(group_id, current_user.id)
    topic_svc = TopicService(db)
    topic = await topic_svc.get_topic_in_group_or_404(topic_id, group_id)
    await topic_svc.assert_author_or_owner(topic, current_user.id)
    media = await topic_svc.confirm_media(
        topic_id=topic_id,
        object_key=body.object_key,
        content_type=body.content_type,
        width=body.width,
        height=body.height,
        byte_size=body.byte_size,
    )
    return media


@router.get("", response_model=list[MediaOut])
async def list_media(
    group_id: str,
    topic_id: str,
    current_user: CurrentUser,
    db: DbSession,
):
    group_svc = GroupService(db)
    await group_svc.require_membership(group_id, current_user.id)
    topic_svc = TopicService(db)
    await topic_svc.get_topic_in_group_or_404(topic_id, group_id)
    return await topic_svc.list_media(topic_id)
