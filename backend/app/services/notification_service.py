"""NotificationService — in-app notifications and push subscriptions.

Real Web Push is sent only when VAPID keys are provisioned (settings.vapid_enabled).
Without keys, send_push is a silent no-op so the demo runs without VAPID
infrastructure — see the env-conditional branch in send_push below.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any

import requests
from pywebpush import webpush
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import NotFoundError
from app.core.push_endpoint import is_safe_push_endpoint
from app.models.notification import Notification
from app.models.push_subscription import PushSubscription
from app.repositories.notification_repository import (
    NotificationRepository,
    PushSubscriptionRepository,
)

logger = logging.getLogger(__name__)

# Web Push tuning. Endpoints are user-provided public HTTPS URLs, so a slow or
# hostile one must not tie up an asyncio.to_thread worker: bound each send with
# a short connect/read timeout. TTL asks the push service to hold the message
# for offline devices instead of dropping it (pywebpush defaults to ttl=0 =
# deliver-now-or-discard, which defeats the point of push for a suspended app).
PUSH_REQUEST_TIMEOUT_SECONDS = 10
PUSH_TTL_SECONDS = 60 * 60 * 24  # 1 day


class _NoRedirectSession(requests.Session):
    """requests session that never follows redirects on a push POST.

    is_safe_push_endpoint only vets the *stored* URL; requests would otherwise
    follow a 3xx to an attacker-controlled internal host (e.g. a public https
    endpoint that 302s to http://169.254.169.254/…), re-opening the SSRF hole.
    With redirects off, such a response just fails the send safely.
    """

    def post(self, url, **kwargs):  # type: ignore[override]
        kwargs.setdefault("allow_redirects", False)
        return super().post(url, **kwargs)


class NotificationService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._notif_repo = NotificationRepository(db)
        self._push_repo = PushSubscriptionRepository(db)

    async def create_notification(
        self,
        user_id: str,
        type: str,
        payload: dict[str, Any],
        dedup_key: str | None = None,
    ) -> Notification:
        notif = await self._notif_repo.create(
            user_id=user_id, type=type, payload=payload, dedup_key=dedup_key
        )
        await self._db.commit()
        await self._db.refresh(notif)
        return notif

    async def bump_topic_unread(
        self,
        group_id: str,
        topic_id: str,
        topic_title: str,
        group_name: str,
        exclude_user_id: str,
        member_user_ids: list[str],
        message_at: datetime,
    ) -> None:
        """Upsert a chat_unread notification for each member except the sender.

        Uses dedup_key=f"chat_unread:{topic_id}" so repeated messages recycle
        the same notification slot instead of accumulating duplicates. The
        notification's created_at is stamped with the triggering message's time
        (``message_at``) so a read receipt up to that message clears it. Commits
        once after all upserts.
        """
        payload: dict[str, Any] = {
            "group_id": group_id,
            "group_name": group_name,
            "topic_id": topic_id,
            "title": topic_title,
        }
        for user_id in member_user_ids:
            if user_id == exclude_user_id:
                continue
            await self._notif_repo.upsert_by_dedup_key(
                user_id=user_id,
                type="chat_unread",
                payload=payload,
                dedup_key=f"chat_unread:{topic_id}",
                created_at=message_at,
            )
        await self._db.commit()

    async def clear_topic_notifications(
        self, user_id: str, topic_id: str, before: datetime | None = None
    ) -> None:
        """Mark new_topic and chat_unread notifications as read for a topic.

        ``new_topic`` ("a topic was posted") is cleared unconditionally — opening
        the topic acknowledges it. Its created_at is the post time (after the
        topic's own timestamp), so a message-time ``before`` cutoff would wrongly
        miss it when reading a message-less seed topic up to topic.created_at.

        ``chat_unread`` (per-message) is bounded by ``before`` (the read point),
        so an alert for a message that arrived after the read receipt survives.
        """
        await self._notif_repo.mark_read_by_dedup_keys(
            user_id=user_id, dedup_keys=[f"new_topic:{topic_id}"]
        )
        await self._notif_repo.mark_read_by_dedup_keys(
            user_id=user_id, dedup_keys=[f"chat_unread:{topic_id}"], before=before
        )
        await self._db.commit()

    async def list_notifications(self, user_id: str, limit: int = 50) -> list[Notification]:
        return await self._notif_repo.list_by_user(user_id, limit=limit)

    @staticmethod
    def _to_view(notif: Notification) -> dict[str, Any]:
        """Derive a client-facing view (title/body/action_url) from type+payload."""
        payload = notif.payload or {}
        if notif.type == "chat_unread":
            # Explicitly handled before new_topic/chat_started to avoid fall-through.
            title_text = payload.get("title", "")
            title = f"{title_text}에 대해 안 읽은 채팅이 있어요"
            body = payload.get("group_name", "")
            gid, tid = payload.get("group_id"), payload.get("topic_id")
            action_url = f"/groups/{gid}/topics/{tid}/chat" if gid and tid else None
        elif notif.type in ("new_topic", "chat_started"):
            author = payload.get("author") or "누군가"
            group_name = payload.get("group_name")
            action = "새로운 주제를 올렸어요" if notif.type == "new_topic" else "채팅을 시작했어요"
            who = f"{author}님이 {action}"
            title = f"{group_name}에서 {who}" if group_name else who
            body = payload.get("title", "")
            gid, tid = payload.get("group_id"), payload.get("topic_id")
            action_url = f"/groups/{gid}/topics/{tid}/chat" if gid and tid else None
        else:
            title = payload.get("title", "알림")
            body = payload.get("body", "")
            action_url = payload.get("action_url")
        return {
            "id": notif.id,
            "user_id": notif.user_id,
            "kind": notif.type,
            "title": title,
            "body": body,
            "action_url": action_url,
            "read": notif.read_at is not None,
            "created_at": notif.created_at,
        }

    async def list_view(self, user_id: str, limit: int = 50) -> tuple[list[dict[str, Any]], int]:
        notifs = await self._notif_repo.list_by_user(user_id, limit=limit)
        unread_count = await self._notif_repo.count_unread(user_id)
        return [self._to_view(n) for n in notifs], unread_count

    async def mark_read(self, notification_id: str, user_id: str) -> Notification:
        notif = await self._notif_repo.get_by_id(notification_id)
        if notif is None:
            raise NotFoundError("Notification", notification_id)
        if notif.user_id != user_id:
            from app.core.exceptions import ForbiddenError

            raise ForbiddenError("Cannot mark another user's notification as read")
        notif = await self._notif_repo.mark_read(notif)
        await self._db.commit()
        return notif

    async def upsert_push_subscription(
        self, user_id: str, endpoint: str, p256dh: str, auth: str
    ) -> PushSubscription:
        sub = await self._push_repo.upsert(
            user_id=user_id, endpoint=endpoint, p256dh=p256dh, auth=auth
        )
        await self._db.commit()
        return sub

    async def delete_user_subscriptions(self, user_id: str) -> None:
        """Remove all push subscriptions for a user (client unsubscribe)."""
        for sub in await self._push_repo.list_by_user(user_id):
            await self._push_repo.delete(sub)
        await self._db.commit()

    async def delete_push_subscription(self, endpoint: str, user_id: str) -> None:
        sub = await self._push_repo.get_by_endpoint(endpoint)
        if sub is None:
            raise NotFoundError("PushSubscription", endpoint)
        if sub.user_id != user_id:
            from app.core.exceptions import ForbiddenError

            raise ForbiddenError("Cannot delete another user's subscription")
        await self._push_repo.delete(sub)
        await self._db.commit()

    async def delete_push_subscription_if_present(self, endpoint: str, user_id: str) -> None:
        """Idempotently remove one device's subscription on client unsubscribe.

        Unlike ``delete_push_subscription`` this does not 404 when the row is
        already gone (the client is merely toggling notifications off), and it
        only deletes a row that belongs to the caller — never another user's.
        """
        sub = await self._push_repo.get_by_endpoint(endpoint)
        if sub is None or sub.user_id != user_id:
            return
        await self._push_repo.delete(sub)
        await self._db.commit()

    async def send_push(self, user_id: str, payload: dict[str, Any]) -> None:
        """Send a Web Push notification to every device the user subscribed from.

        ``payload`` must match the service worker's push contract:
        ``{"title": str, "body": str, "url": str}``.

        Real delivery only runs when VAPID keys are provisioned
        (settings.vapid_enabled); without keys this is a silent no-op so the
        demo/dev environment works without push infrastructure provisioned.

        The subscription rows are read and the DB connection released (rollback
        — nothing to persist yet) *before* any network I/O, so a slow endpoint
        can't hold a pool connection for up to the timeout per send and starve
        the small async pool during fan-out. pywebpush performs a synchronous
        HTTP call (via `requests`), so each send is offloaded to a worker thread
        with `asyncio.to_thread`. A 404/410 response (or an unsafe/dead
        endpoint) means the subscription should go; those are pruned together in
        one short transaction afterwards. Any other failure is logged and does
        not stop delivery to the user's remaining devices.
        """
        settings = get_settings()
        if not settings.vapid_enabled:
            # No VAPID keys configured: fallback no-op for demo/dev.
            return

        subs = await self._push_repo.list_by_user(user_id)
        # Snapshot plain values (incl. the id) while the session is live, then
        # release the read connection. We must NOT carry ORM instances past the
        # rollback below: rollback expires them, so a later attribute access
        # would trigger implicit async I/O and raise MissingGreenlet.
        targets = [(sub.id, sub.endpoint, sub.p256dh, sub.auth) for sub in subs]
        await self._db.rollback()

        data = json.dumps(payload)
        to_prune: list[str] = []
        for sub_id, endpoint, p256dh, auth in targets:
            # Defence in depth: re-validate the stored endpoint before an
            # outbound request. The subscribe-time validator only guards new
            # POSTs; a row written before it existed (or inserted directly)
            # could carry a private/loopback endpoint, which would turn this
            # send into an SSRF. Prune such a row — it can never deliver.
            if not is_safe_push_endpoint(endpoint):
                logger.warning(
                    "pruning push subscription %s (user %s): unsafe endpoint",
                    sub_id,
                    user_id,
                )
                to_prune.append(sub_id)
                continue
            subscription_info = {
                "endpoint": endpoint,
                "keys": {"p256dh": p256dh, "auth": auth},
            }
            # pywebpush mutates vapid_claims in place (adds aud/exp), so each
            # subscription needs its own fresh dict.
            vapid_claims: dict[str, str | int] = {"sub": f"mailto:{settings.vapid_claim_email}"}
            try:
                await asyncio.to_thread(
                    webpush,
                    subscription_info=subscription_info,
                    data=data,
                    vapid_private_key=settings.vapid_private_key,
                    vapid_claims=vapid_claims,
                    ttl=PUSH_TTL_SECONDS,
                    timeout=PUSH_REQUEST_TIMEOUT_SECONDS,
                    # Fresh per-send session (requests.Session isn't guaranteed
                    # thread-safe under asyncio.to_thread) that refuses redirects.
                    requests_session=_NoRedirectSession(),
                )
            except Exception as exc:  # noqa: BLE001 - one bad sub must not break the batch
                # WebPushException carries a response with the push service's
                # status; any other exception (e.g. network error) has none.
                status_code = getattr(getattr(exc, "response", None), "status_code", None)
                if status_code in (404, 410):
                    to_prune.append(sub_id)
                else:
                    logger.warning(
                        "push send failed for subscription %s (user %s): %s",
                        sub_id,
                        user_id,
                        exc,
                    )

        # Prune revoked/unsafe rows by id in one short transaction after the
        # network I/O (no ORM instances survive the rollback above).
        for sub_id in to_prune:
            await self._push_repo.delete_by_id(sub_id)
        if to_prune:
            await self._db.commit()
