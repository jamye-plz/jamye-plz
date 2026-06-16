"""NotificationRepository and PushSubscriptionRepository."""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification
from app.models.push_subscription import PushSubscription


class NotificationRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_id(self, notification_id: str) -> Notification | None:
        result = await self._db.execute(
            select(Notification).where(Notification.id == notification_id)
        )
        return result.scalar_one_or_none()

    async def create(self, user_id: str, type: str, payload: dict[str, Any]) -> Notification:
        notification = Notification(user_id=user_id, type=type, payload=payload)
        self._db.add(notification)
        await self._db.flush()
        await self._db.refresh(notification)
        return notification

    async def list_by_user(self, user_id: str, limit: int = 50) -> list[Notification]:
        result = await self._db.execute(
            select(Notification)
            .where(Notification.user_id == user_id)
            .order_by(Notification.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def mark_read(self, notification: Notification) -> Notification:
        notification.read_at = datetime.now(timezone.utc)
        self._db.add(notification)
        await self._db.flush()
        await self._db.refresh(notification)
        return notification


class PushSubscriptionRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_endpoint(self, endpoint: str) -> PushSubscription | None:
        result = await self._db.execute(
            select(PushSubscription).where(PushSubscription.endpoint == endpoint)
        )
        return result.scalar_one_or_none()

    async def upsert(self, user_id: str, endpoint: str, p256dh: str, auth: str) -> PushSubscription:
        existing = await self.get_by_endpoint(endpoint)
        if existing:
            existing.p256dh = p256dh
            existing.auth = auth
            self._db.add(existing)
            await self._db.flush()
            await self._db.refresh(existing)
            return existing
        sub = PushSubscription(user_id=user_id, endpoint=endpoint, p256dh=p256dh, auth=auth)
        self._db.add(sub)
        await self._db.flush()
        await self._db.refresh(sub)
        return sub

    async def delete(self, sub: PushSubscription) -> None:
        await self._db.delete(sub)
        await self._db.flush()

    async def list_by_user(self, user_id: str) -> list[PushSubscription]:
        result = await self._db.execute(
            select(PushSubscription).where(PushSubscription.user_id == user_id)
        )
        return list(result.scalars().all())
