"""Voice-message transcription worker (M4a).

Runs as a separate process:  `uv run arq app.workers.transcribe.WorkerSettings`

Pipeline per job: fetch the audio object from MinIO → run faster-whisper on a
thread (CPU-bound) → store transcript/status on the message_media row →
publish the result on the Redis bridge channel, where the API server's
lifespan subscriber broadcasts it to the chatroom over WebSocket (the worker
cannot reach the API's in-memory ws_hub directly).

faster-whisper is imported lazily inside the model loader so that importing
this module (tests, tooling) never pays for — or fails on — the STT stack.
"""

import asyncio
import io
import json
import logging
from typing import Any

from arq.connections import RedisSettings
from sqlalchemy import select

from app.core import storage
from app.core.config import get_settings
from app.core.queue import TRANSCRIPT_CHANNEL
from app.db.session import get_db
from app.models.message import Message
from app.models.message_media import MessageMedia

logger = logging.getLogger(__name__)

_model: Any = None


def _get_model() -> Any:
    """Process-wide model singleton. Loading takes seconds and ~GBs of RAM,
    so it must happen once per worker process, not once per job."""
    global _model
    if _model is None:
        from faster_whisper import WhisperModel  # lazy: worker-only dependency path

        settings = get_settings()
        logger.info(
            "Loading STT model %s (compute_type=%s)", settings.stt_model, settings.stt_compute_type
        )
        _model = WhisperModel(
            settings.stt_model, device="cpu", compute_type=settings.stt_compute_type
        )
    return _model


def _download(object_key: str) -> bytes:
    """Sync boto3 fetch — call via asyncio.to_thread."""
    settings = get_settings()
    obj = storage.get_s3_client().get_object(Bucket=settings.minio_bucket, Key=object_key)
    return obj["Body"].read()


def _transcribe_bytes(data: bytes) -> str:
    """Sync, CPU-bound — call via asyncio.to_thread.

    language="ko" is forced: every user is Korean, and auto-detect on short
    clips is exactly where Whisper mis-detects and leaks English. vad_filter
    trims silence, Whisper's best-known hallucination trigger.
    """
    model = _get_model()
    segments, _info = model.transcribe(
        io.BytesIO(data),
        language="ko",
        vad_filter=True,
        beam_size=5,
        condition_on_previous_text=False,
    )
    # segments is a lazy generator; joining consumes (and thus runs) it here,
    # inside the worker thread, not on the event loop.
    return " ".join(seg.text.strip() for seg in segments).strip()


async def transcribe(ctx: dict[str, Any], media_id: str) -> None:
    """arq task: transcribe one audio attachment and publish the result."""
    async for db in get_db():
        row = (
            await db.execute(
                select(MessageMedia, Message.chatroom_id)
                .join(Message, Message.id == MessageMedia.message_id)
                .where(MessageMedia.id == media_id)
            )
        ).first()
        if row is None:
            # Deleted between enqueue and execution — nothing to do.
            logger.info("Media %s vanished before transcription", media_id)
            return
        media, chatroom_id = row

        try:
            data = await asyncio.to_thread(_download, media.object_key)
            text = await asyncio.to_thread(_transcribe_bytes, data)
            media.transcript = text
            media.transcript_status = "done"
        except Exception:
            # Store the failure so the UI stops showing "transcribing…" —
            # a crash here must not leave the row pending forever.
            logger.exception("Transcription failed for media %s", media_id)
            media.transcript_status = "failed"
        await db.commit()

        # Publish AFTER the commit so a subscriber acting on the event always
        # sees the persisted state. ctx["redis"] is arq's own pool.
        await ctx["redis"].publish(
            TRANSCRIPT_CHANNEL,
            json.dumps(
                {
                    "chatroom_id": chatroom_id,
                    "message_id": media.message_id,
                    "media_id": media.id,
                    "status": media.transcript_status,
                    "transcript": media.transcript,
                }
            ),
        )
        break


def _redis_settings() -> RedisSettings | None:
    """None (arq's localhost default) when REDIS_URL is unset, so importing
    this module never raises — the worker is only ever launched deliberately."""
    url = get_settings().redis_url
    return RedisSettings.from_dsn(url) if url else None


class WorkerSettings:
    functions = [transcribe]
    redis_settings = _redis_settings()
    # A 5-minute voice message transcribes in well under 2 minutes on CPU with
    # the turbo model; 10 minutes covers the first-run model download too.
    job_timeout = 600
    max_tries = 3
    # Transcription is CPU-bound and the model is a per-process singleton —
    # one job at a time keeps memory bounded (one model + one decode buffer).
    max_jobs = 1
