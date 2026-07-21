"""Push subscription router — Web Push VAPID management."""

import base64
import binascii

from fastapi import APIRouter
from pydantic import BaseModel, Field, field_validator

from app.core.config import get_settings
from app.core.deps import CurrentUser, DbSession
from app.core.push_endpoint import is_safe_push_endpoint
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/push", tags=["push"])

# Web Push key sizes (RFC 8291 / 8292): p256dh is an uncompressed P-256 public
# key (65 bytes), auth is 16 random bytes. Validating these at subscribe time
# stops a client from storing malformed/oversized keys that would make pywebpush
# raise on EVERY send (no HTTP response → the row is logged, never pruned, and
# retried indefinitely).
_P256DH_BYTES = 65
_AUTH_BYTES = 16


def _b64url_decoded_len(value: str) -> int | None:
    """Decoded byte length of a base64url string (padding optional), or None
    if it isn't valid base64url."""
    try:
        return len(base64.urlsafe_b64decode(value + "=" * (-len(value) % 4)))
    except (binascii.Error, ValueError):
        return None


class PushSubscribeBody(BaseModel):
    endpoint: str
    p256dh: str = Field(max_length=128)
    auth: str = Field(max_length=64)

    @field_validator("endpoint")
    @classmethod
    def validate_endpoint(cls, v: str) -> str:
        if not is_safe_push_endpoint(v):
            raise ValueError("push endpoint must be a public https URL")
        return v

    @field_validator("p256dh")
    @classmethod
    def validate_p256dh(cls, v: str) -> str:
        if _b64url_decoded_len(v) != _P256DH_BYTES:
            raise ValueError("p256dh must be a base64url-encoded 65-byte P-256 key")
        return v

    @field_validator("auth")
    @classmethod
    def validate_auth(cls, v: str) -> str:
        if _b64url_decoded_len(v) != _AUTH_BYTES:
            raise ValueError("auth must be a base64url-encoded 16-byte secret")
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
