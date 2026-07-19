"""Fire-and-forget Web Push dispatch for request/WS flows.

``dispatch_push`` is the coroutine that actually delivers the push: it opens
its own AsyncSession (a request/WS-scoped session must never be shared across
concurrent tasks — see backend rule "safe ORM lifecycle") and swallows every
exception, since a push delivery failure must never surface to the HTTP/WS
caller that triggered it.

``schedule_push_dispatch`` is the entry point request/WS flows should call:
it wraps ``dispatch_push`` in ``asyncio.create_task`` and keeps a strong
reference to the task until it finishes. asyncio only holds a weak reference
to a scheduled task, so an unreferenced task can be garbage-collected
mid-flight, silently dropping the push and logging a "Task was destroyed but
it is pending" warning.
"""

import asyncio
import logging
from typing import Any

from app.db.session import _get_session_factory
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)

# Strong references to in-flight dispatch tasks, so they aren't GC'd before
# they complete. Each task removes itself once done.
_background_tasks: set[asyncio.Task[None]] = set()


async def dispatch_push(user_ids: list[str], payload: dict[str, Any]) -> None:
    """Send ``payload`` as a Web Push to each user in ``user_ids``.

    Safe to schedule via ``asyncio.create_task(dispatch_push(...))`` from a
    request/WS flow without awaiting it: opens its own AsyncSession (never
    reuses the caller's request-scoped session) and never raises — every
    failure (session setup, a bad payload, a per-user send error not already
    absorbed by ``NotificationService.send_push``) is caught and logged here.
    """
    try:
        session_factory = _get_session_factory()
        async with session_factory() as db:
            svc = NotificationService(db)
            for user_id in user_ids:
                try:
                    await svc.send_push(user_id, payload)
                except Exception:
                    logger.warning("push dispatch failed for user %s", user_id, exc_info=True)
    except Exception:
        logger.warning("push dispatch failed to start", exc_info=True)


def schedule_push_dispatch(user_ids: list[str], payload: dict[str, Any]) -> None:
    """Schedule ``dispatch_push`` without blocking the caller.

    No-op when ``user_ids`` is empty. Must not be awaited by callers — it
    returns as soon as the task is scheduled.
    """
    if not user_ids:
        return
    task = asyncio.create_task(dispatch_push(user_ids, payload))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
