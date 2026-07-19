"""Push subscription router — Web Push VAPID management."""

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.deps import CurrentUser, DbSession
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/push", tags=["push"])


class PushSubscribeBody(BaseModel):
    endpoint: str
    p256dh: str
    auth: str


class VapidPublicKeyOut(BaseModel):
    public_key: str


@router.get("/vapid-public-key", response_model=VapidPublicKeyOut)
async def get_vapid_public_key() -> VapidPublicKeyOut:
    """Public VAPID key for the frontend's PushManager.subscribe applicationServerKey.

    Returns an empty string when VAPID isn't provisioned so the frontend can
    hide the push opt-in toggle instead of erroring.
    """
    settings = get_settings()
    return VapidPublicKeyOut(public_key=settings.vapid_public_key)


@router.post("/subscribe", status_code=204)
async def subscribe_push(body: PushSubscribeBody, current_user: CurrentUser, db: DbSession):
    svc = NotificationService(db)
    await svc.upsert_push_subscription(
        user_id=current_user.id,
        endpoint=body.endpoint,
        p256dh=body.p256dh,
        auth=body.auth,
    )


@router.delete("/subscribe", status_code=204)
async def unsubscribe_push(current_user: CurrentUser, db: DbSession):
    """Remove the current user's push subscription(s)."""
    svc = NotificationService(db)
    await svc.delete_user_subscriptions(current_user.id)
