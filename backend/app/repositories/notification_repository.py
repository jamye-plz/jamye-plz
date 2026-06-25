"""NotificationRepository and PushSubscriptionRepository."""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
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

    async def create(
        self,
        user_id: str,
        type: str,
        payload: dict[str, Any],
        dedup_key: str | None = None,
    ) -> Notification:
        notification = Notification(
            user_id=user_id, type=type, payload=payload, dedup_key=dedup_key
        )
        self._db.add(notification)
        await self._db.flush()
        await self._db.refresh(notification)
        return notification

    async def get_by_dedup_key(self, user_id: str, dedup_key: str) -> Notification | None:
        result = await self._db.execute(
            select(Notification).where(
                Notification.user_id == user_id,
                Notification.dedup_key == dedup_key,
            )
        )
        return result.scalar_one_or_none()

    async def upsert_by_dedup_key(
        self, user_id: str, type: str, payload: dict[str, Any], dedup_key: str
    ) -> Notification:
        """Atomically recycle the (user_id, dedup_key) notification slot.

        Uses Postgres ``INSERT ... ON CONFLICT DO UPDATE`` against the partial
        unique index so concurrent upserts for the same slot (e.g. two senders
        posting in one topic at once, before any recipient row exists) can't race
        into an IntegrityError. On conflict the existing row is refreshed: its
        payload/type are updated, read_at is reset, and created_at is bumped to
        now so it resurfaces as unread.
        """
        now = datetime.now(timezone.utc)
        stmt = (
            pg_insert(Notification)
            .values(
                id=str(uuid.uuid4()),
                user_id=user_id,
                type=type,
                payload=payload,
                dedup_key=dedup_key,
                read_at=None,
                created_at=now,
            )
            .on_conflict_do_update(
                index_elements=[Notification.user_id, Notification.dedup_key],
                index_where=Notification.dedup_key.isnot(None),
                set_={
                    "type": type,
                    "payload": payload,
                    "read_at": None,
                    "created_at": now,
                },
            )
        )
        await self._db.execute(stmt)
        await self._db.flush()
        notif = await self.get_by_dedup_key(user_id, dedup_key)
        assert notif is not None  # row was just upserted within this transaction
        # The Core ON CONFLICT statement bypasses the ORM unit of work, so an
        # already-identity-mapped row would otherwise return stale attributes.
        await self._db.refresh(notif)
        return notif

    async def mark_read_by_dedup_keys(self, user_id: str, dedup_keys: list[str]) -> None:
        """Set read_at=now for all matching unread notifications."""
        if not dedup_keys:
            return
        result = await self._db.execute(
            select(Notification).where(
                Notification.user_id == user_id,
                Notification.dedup_key.in_(dedup_keys),
                Notification.read_at.is_(None),
            )
        )
        now = datetime.now(timezone.utc)
        for notif in result.scalars().all():
            notif.read_at = now
            self._db.add(notif)
        await self._db.flush()

    async def list_by_user(self, user_id: str, limit: int = 50) -> list[Notification]:
        result = await self._db.execute(
            select(Notification)
            .where(Notification.user_id == user_id)
            .order_by(Notification.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def count_unread(self, user_id: str) -> int:
        result = await self._db.execute(
            select(func.count())
            .select_from(Notification)
            .where(Notification.user_id == user_id, Notification.read_at.is_(None))
        )
        return int(result.scalar_one())

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
