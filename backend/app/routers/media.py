"""Media router — presign and confirm media uploads.

Real presign URLs are generated only when MinIO/S3 keys are provisioned.
# TODO(oma-deferred): integrate minio when key is provisioned
"""

import uuid

from fastapi import APIRouter

from app.core.config import get_settings
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
    await TopicService(db).get_topic_in_group_or_404(topic_id, group_id)

    settings = get_settings()
    object_key = f"topics/{topic_id}/{uuid.uuid4()}"

    if settings.minio_enabled:
        # TODO(oma-deferred): integrate minio when key is provisioned
        raise NotImplementedError("MinIO presign real path not implemented")

    # Fallback: return a stub upload URL for demo
    return MediaPresignOut(
        object_key=object_key,
        upload_url=f"http://localhost:9000/{settings.minio_bucket}/{object_key}",
        expires_in=3600,
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
    await TopicService(db).get_topic_in_group_or_404(topic_id, group_id)
    topic_svc = TopicService(db)
    media = await topic_svc.confirm_media(
        topic_id=topic_id,
        object_key=body.object_key,
        content_type="image",
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
    await TopicService(db).get_topic_in_group_or_404(topic_id, group_id)
    topic_svc = TopicService(db)
    return await topic_svc.list_media(topic_id)
