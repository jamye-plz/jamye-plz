"""NotificationService — in-app notifications and push subscriptions.

Real Web Push is sent only when VAPID keys are provisioned.
# TODO(oma-deferred): integrate vapid when key is provisioned
"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import NotFoundError
from app.models.notification import Notification
from app.models.push_subscription import PushSubscription
from app.repositories.notification_repository import (
    NotificationRepository,
    PushSubscriptionRepository,
)


class NotificationService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._notif_repo = NotificationRepository(db)
        self._push_repo = PushSubscriptionRepository(db)

    async def create_notification(
        self, user_id: str, type: str, payload: dict[str, Any]
    ) -> Notification:
        notif = await self._notif_repo.create(user_id=user_id, type=type, payload=payload)
        await self._db.commit()
        await self._db.refresh(notif)
        return notif

    async def list_notifications(self, user_id: str, limit: int = 50) -> list[Notification]:
        return await self._notif_repo.list_by_user(user_id, limit=limit)

    @staticmethod
    def _to_view(notif: Notification) -> dict[str, Any]:
        """Derive a client-facing view (title/body/action_url) from type+payload."""
        payload = notif.payload or {}
        if notif.type in ("new_topic", "chat_started"):
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

    async def send_push(self, user_id: str, payload: dict[str, Any]) -> None:
        settings = get_settings()
        if settings.vapid_enabled:
            # TODO(oma-deferred): integrate vapid when key is provisioned
            # Real path: fetch user's push subscriptions, send via pywebpush
            raise NotImplementedError("VAPID push real path not implemented")
        # Fallback: no-op for demo
        pass
