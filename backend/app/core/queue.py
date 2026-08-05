"""arq/Redis wiring for async transcription (M4a).

Env-conditional per backend.md rule 11: everything here is a no-op when
REDIS_URL is unset. Voice messages then simply go untranscribed
(transcript_status stays NULL) — the demo keeps working with no queue
provisioned.
"""

import logging
from typing import Any

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# Worker → backend bridge channel. The arq worker runs in a separate process
# and cannot reach the backend's in-memory ws_hub, so it publishes transcript
# results here and the backend's lifespan subscriber broadcasts them over WS.
TRANSCRIPT_CHANNEL = "jamye:transcripts"

_pool: ArqRedis | None = None


async def get_arq_pool() -> ArqRedis | None:
    """Lazily created, process-wide arq pool. None when Redis is not configured."""
    global _pool
    settings = get_settings()
    if not settings.transcription_enabled:
        return None
    if _pool is None:
        _pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    return _pool


async def close_arq_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.aclose()
        _pool = None


async def enqueue_transcription(media_id: str) -> None:
    """Fire-and-forget enqueue. MUST never break the message send.

    The message is already committed by the time this runs; a queue hiccup
    should degrade to "no transcript" (the documented fallback), not to a
    failed send. Errors are logged, not raised.
    """
    try:
        pool = await get_arq_pool()
        if pool is None:
            return
        await pool.enqueue_job("transcribe", media_id)
    except Exception:
        logger.warning("Failed to enqueue transcription for media %s", media_id, exc_info=True)


def parse_transcript_event(raw: bytes | str) -> dict[str, Any] | None:
    """Validate a bridge message into the WS `transcript` frame payload.

    The channel is trusted (same Redis, written only by our worker), but a
    malformed event must not kill the subscriber loop — return None instead.
    """
    import json

    try:
        data = json.loads(raw)
        return {
            "type": "transcript",
            "chatroom_id": str(data["chatroom_id"]),
            "message_id": str(data["message_id"]),
            "media_id": str(data["media_id"]),
            "status": str(data["status"]),
            "transcript": data.get("transcript"),
        }
    except (ValueError, KeyError, TypeError):
        logger.warning("Malformed transcript event dropped: %r", raw)
        return None
