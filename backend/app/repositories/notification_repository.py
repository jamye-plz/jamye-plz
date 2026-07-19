"""NotificationRepository and PushSubscriptionRepository."""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import case, func, select, update
from sqlalchemy import delete as sa_delete
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
        self,
        user_id: str,
        type: str,
        payload: dict[str, Any],
        dedup_key: str,
        created_at: datetime | None = None,
    ) -> Notification:
        """Atomically recycle the (user_id, dedup_key) notification slot.

        Uses Postgres ``INSERT ... ON CONFLICT DO UPDATE`` against the partial
        unique index so concurrent upserts for the same slot (e.g. two senders
        posting in one topic at once, before any recipient row exists) can't race
        into an IntegrityError. On conflict the existing row is refreshed: its
        payload/type are updated, read_at is reset, and created_at is set to
        ``created_at`` so it resurfaces as unread.

        ``created_at`` should be the triggering message's timestamp (not now), so
        a read receipt recorded up to that message's time correctly covers — and
        clears — this notification. Defaults to now when omitted.
        """
        ts = created_at or datetime.now(timezone.utc)
        insert_stmt = pg_insert(Notification).values(
            id=str(uuid.uuid4()),
            user_id=user_id,
            type=type,
            payload=payload,
            dedup_key=dedup_key,
            read_at=None,
            created_at=ts,
        )
        excluded_created = insert_stmt.excluded.created_at
        stmt = insert_stmt.on_conflict_do_update(
            index_elements=[Notification.user_id, Notification.dedup_key],
            index_where=Notification.dedup_key.isnot(None),
            set_={
                "type": type,
                "payload": payload,
                # Keep the slot monotonic by message time: an out-of-order older
                # message must not move created_at back (which would let a read of
                # only the older message clear the alert for an unseen newer one).
                "created_at": func.greatest(Notification.created_at, excluded_created),
                # Only resurface as unread when this really is a newer message.
                "read_at": case(
                    (excluded_created > Notification.created_at, None),
                    else_=Notification.read_at,
                ),
            },
        )
        await self._db.execute(stmt)
        await self._db.flush()
        notif = await self.get_by_dedup_key(user_id, dedup_key)
        assert notif is not None  # row was just upserted within this transaction
        # The Core ON CONFLICT statement bypasses the ORM unit of work, so an
        # already-identity-mapped row would otherwise return stale attributes.
        await self._db.refresh(notif)
        return notif

    async def mark_read_by_dedup_keys(
        self, user_id: str, dedup_keys: list[str], before: datetime | None = None
    ) -> None:
        """Set read_at=now for matching unread notifications.

        When ``before`` is given, only notifications created at or before that
        instant are cleared. This keeps a read receipt from silencing an alert
        for a message that arrived after the receipt was recorded (the topic
        would still compute as unread, so the notification must survive).
        """
        if not dedup_keys:
            return
        conditions = [
            Notification.user_id == user_id,
            Notification.dedup_key.in_(dedup_keys),
            Notification.read_at.is_(None),
        ]
        if before is not None:
            conditions.append(Notification.created_at <= before)
        # Single predicated UPDATE: the `created_at <= before` bound is enforced
        # at write time under row locks, so a row concurrently recycled past
        # `before` (its created_at bumped) no longer matches and is left unread.
        stmt = (
            update(Notification)
            .where(*conditions)
            .values(read_at=datetime.now(timezone.utc))
            .execution_options(synchronize_session=False)
        )
        await self._db.execute(stmt)
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
        # Atomic INSERT ... ON CONFLICT (endpoint) DO UPDATE. A browser push
        # subscription is device-scoped and unique by endpoint; whoever
        # currently controls this browser owns the row, so on conflict we
        # reassign user_id (a second account on the same browser must not
        # inherit or be shadowed by the previous user's row). Doing this as a
        # single statement — rather than SELECT-then-INSERT — means two
        # concurrent POSTs for the same endpoint (e.g. the global reclaim racing
        # Settings' own reconcile) can't both miss the row and 500 on the unique
        # constraint; one updates, the other conflict-updates.
        insert_stmt = pg_insert(PushSubscription).values(
            id=str(uuid.uuid4()),
            user_id=user_id,
            endpoint=endpoint,
            p256dh=p256dh,
            auth=auth,
        )
        stmt = insert_stmt.on_conflict_do_update(
            index_elements=[PushSubscription.endpoint],
            # Bump created_at on re-register so this device counts as most-recent
            # for the per-user cap prune (prune_to_limit) — a device that just
            # re-subscribed must never be the one pruned.
            set_={"user_id": user_id, "p256dh": p256dh, "auth": auth, "created_at": func.now()},
        ).returning(PushSubscription)
        result = await self._db.execute(stmt)
        return result.scalar_one()

    async def prune_to_limit(self, user_id: str, limit: int) -> None:
        """Keep only the `limit` most-recently-registered subscriptions for a
        user, deleting the rest.

        Bounds per-user push fan-out: without a cap an account could register
        hundreds of (slow) endpoints and make every group notification spend up
        to timeout*N on it, starving other recipients. Real users have a handful
        of devices.
        """
        keep = (
            select(PushSubscription.id)
            .where(PushSubscription.user_id == user_id)
            .order_by(PushSubscription.created_at.desc(), PushSubscription.id.desc())
            .limit(limit)
            .scalar_subquery()
        )
        await self._db.execute(
            sa_delete(PushSubscription).where(
                PushSubscription.user_id == user_id,
                PushSubscription.id.not_in(keep),
            )
        )

    async def delete(self, sub: PushSubscription) -> None:
        await self._db.delete(sub)
        await self._db.flush()

    async def delete_by_id(self, sub_id: str) -> None:
        """Delete by primary key without needing a live ORM instance.

        Lets callers prune a subscription after they've released the read
        transaction (e.g. send_push snapshots ids, does network I/O, then
        prunes) — carrying an ORM instance across a rollback would expire it
        and trigger MissingGreenlet on attribute access.
        """
        await self._db.execute(sa_delete(PushSubscription).where(PushSubscription.id == sub_id))

    async def list_by_user(self, user_id: str) -> list[PushSubscription]:
        result = await self._db.execute(
            select(PushSubscription).where(PushSubscription.user_id == user_id)
        )
        return list(result.scalars().all())
