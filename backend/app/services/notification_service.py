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
