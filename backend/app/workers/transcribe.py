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
    """Sync boto3 fetch — call via asyncio.to_thread.

    The size check here is the AUTHORITATIVE audio cap. The client-declared
    byte_size on the WS frame is untrusted, and the presign cap can be evaded
    by presigning under a laxer MIME (video allows 50 MiB) and re-declaring
    the attachment as audio — so the only number that counts is the stored
    object's actual ContentLength, checked before a single byte is decoded.
    Without this, one crafted message parks the single-job worker on a
    10-minute decode, repeatably.
    """
    settings = get_settings()
    obj = storage.get_s3_client().get_object(Bucket=settings.minio_bucket, Key=object_key)
    size = obj.get("ContentLength")
    if size is None or size > storage.MAX_AUDIO_BYTES:
        raise ValueError(f"audio object {object_key} is {size} bytes, over the transcription cap")
    return obj["Body"].read()


def _probe_duration_seconds(data: bytes) -> float:
    """Container-level duration probe — no decoding. Call via asyncio.to_thread.

    The byte cap cannot bound work: low-bitrate opus fits hours into 15 MiB.
    Header duration is preferred, but MediaRecorder's webm notoriously omits
    it (the same reason the composer measures elapsed time itself) — then the
    packets are demuxed WITHOUT decoding and their durations summed, which is
    I/O-bound and cheap compared to transcription.

    Raises when no duration can be established: an unmeasurable file does not
    get to spend the worker's decode budget (fail closed → status=failed; the
    audio itself stays playable in chat).
    """
    import av  # lazy, mirrors the faster_whisper import: worker-only path

    with av.open(io.BytesIO(data), metadata_errors="ignore") as container:
        if container.duration is not None:
            return container.duration / av.time_base
        stream = next((s for s in container.streams if s.type == "audio"), None)
        if stream is None:
            raise ValueError("no audio stream in attachment")
        total = 0.0
        for packet in container.demux(stream):
            if packet.duration is not None and packet.time_base is not None:
                total += float(packet.duration * packet.time_base)
        if total <= 0.0:
            raise ValueError("audio duration could not be determined")
        return total


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

        # arq retries the WHOLE job when anything after the commit fails
        # (e.g. a transient publish error). The row is already terminal then —
        # redoing the download+decode would waste the single job slot, so a
        # retry only re-publishes.
        if media.transcript_status in ("done", "failed"):
            await _publish(ctx, chatroom_id, media)
            return

        try:
            data = await asyncio.to_thread(_download, media.object_key)
            duration = await asyncio.to_thread(_probe_duration_seconds, data)
            if duration > storage.MAX_AUDIO_SECONDS:
                raise ValueError(
                    f"audio is {duration:.0f}s, over the {storage.MAX_AUDIO_SECONDS}s cap"
                )
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
        # sees the persisted state.
        await _publish(ctx, chatroom_id, media)
        break


async def _publish(ctx: dict[str, Any], chatroom_id: str, media: MessageMedia) -> None:
    """Emit the bridge event. ctx["redis"] is arq's own pool."""
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
