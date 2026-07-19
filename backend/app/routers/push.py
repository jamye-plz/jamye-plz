"""Push subscription router — Web Push VAPID management."""

from fastapi import APIRouter
from pydantic import BaseModel, field_validator

from app.core.config import get_settings
from app.core.deps import CurrentUser, DbSession
from app.core.push_endpoint import is_safe_push_endpoint
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/push", tags=["push"])


class PushSubscribeBody(BaseModel):
    endpoint: str
    p256dh: str
    auth: str

    @field_validator("endpoint")
    @classmethod
    def validate_endpoint(cls, v: str) -> str:
        if not is_safe_push_endpoint(v):
            raise ValueError("push endpoint must be a public https URL")
        return v


class PushUnsubscribeBody(BaseModel):
    endpoint: str | None = None


class VapidPublicKeyOut(BaseModel):
    public_key: str


@router.get("/vapid-public-key", response_model=VapidPublicKeyOut)
async def get_vapid_public_key() -> VapidPublicKeyOut:
    """Public VAPID key for the frontend's PushManager.subscribe applicationServerKey.

    Returns an empty string unless VAPID is *fully* provisioned
    (settings.vapid_enabled requires both keys). A half-configured pair — only
    the public key set — would otherwise show the push toggle and let users
    subscribe even though send_push can never deliver (it no-ops without the
    private key). The empty string makes the frontend hide the toggle instead.
    """
    settings = get_settings()
    key = settings.vapid_public_key if settings.vapid_enabled else ""
    return VapidPublicKeyOut(public_key=key)


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
async def unsubscribe_push(
    current_user: CurrentUser,
    db: DbSession,
    body: PushUnsubscribeBody | None = None,
):
    """Remove push subscriptions for the current user.

    With an ``endpoint`` only that device's subscription is removed, so turning
    the toggle off on one browser doesn't silently kill delivery to the user's
    other devices. Without one (legacy callers) all of the user's rows go.
    """
    svc = NotificationService(db)
    if body is not None and body.endpoint:
        await svc.delete_push_subscription_if_present(body.endpoint, current_user.id)
    else:
        await svc.delete_user_subscriptions(current_user.id)
