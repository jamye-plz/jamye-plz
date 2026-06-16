"""Push subscription router — Web Push VAPID management."""

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.deps import CurrentUser, DbSession
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/push", tags=["push"])


class PushSubscribeBody(BaseModel):
    endpoint: str
    p256dh: str
    auth: str


class PushUnsubscribeBody(BaseModel):
    endpoint: str


@router.post("/subscribe", status_code=204)
async def subscribe_push(body: PushSubscribeBody, current_user: CurrentUser, db: DbSession):
    svc = NotificationService(db)
    await svc.upsert_push_subscription(
        user_id=current_user.id,
        endpoint=body.endpoint,
        p256dh=body.p256dh,
        auth=body.auth,
    )


@router.post("/unsubscribe", status_code=204)
async def unsubscribe_push(body: PushUnsubscribeBody, current_user: CurrentUser, db: DbSession):
    svc = NotificationService(db)
    await svc.delete_push_subscription(endpoint=body.endpoint, user_id=current_user.id)
