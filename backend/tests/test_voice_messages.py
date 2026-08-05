"""Voice message (M4a) tests.

Covers what can actually break:
  1. audio validation — allowlist/cap, and the "audio rides alone" rule,
  2. the enqueue contract — pending is marked and the job queued ONLY when
     Redis is configured; with it absent a voice message still sends,
  3. the worker→backend bridge event parsing,
  4. filename persistence and its use in downloads (tech debt #8).
"""

from types import SimpleNamespace

import pytest
from pydantic import ValidationError as PydanticValidationError

import app.services.chat_service as chat_service_module
from app.core import storage
from app.core.queue import parse_transcript_event
from app.schemas.chat import MessageMediaIn
from app.services.chat_service import ChatService
from tests.test_chat_media import (
    CHATROOM_ID,
    USER_ID,
    FakeDb,
    FakeMediaRepo,
    FakeMessageRepo,
    key_for,
    media_in,
)


def make_service() -> ChatService:
    svc = ChatService(FakeDb())
    svc._message_repo = FakeMessageRepo()  # type: ignore[attr-defined]
    svc._media_repo = FakeMediaRepo()  # type: ignore[attr-defined]
    return svc


# ── Audio validation ──────────────────────────────────────────────────────────


def test_audio_mimes_are_allowed() -> None:
    for mime in ("audio/webm", "audio/mp4", "audio/ogg"):
        m = MessageMediaIn(object_key=key_for(CHATROOM_ID), content_type=mime, duration=42)
        assert m.content_type == mime


def test_audio_over_cap_is_rejected() -> None:
    with pytest.raises(PydanticValidationError):
        MessageMediaIn(
            object_key=key_for(CHATROOM_ID),
            content_type="audio/webm",
            byte_size=storage.MAX_AUDIO_BYTES + 1,
        )


def test_audio_within_cap_is_allowed() -> None:
    m = MessageMediaIn(
        object_key=key_for(CHATROOM_ID),
        content_type="audio/webm",
        byte_size=storage.MAX_AUDIO_BYTES,
    )
    assert m.byte_size == storage.MAX_AUDIO_BYTES


async def test_audio_mixed_with_image_is_rejected() -> None:
    svc = make_service()
    with pytest.raises(chat_service_module.ValidationError):
        await svc.send_message(
            chatroom_id=CHATROOM_ID,
            sender_id=USER_ID,
            body="",
            media=[
                media_in(key_for(CHATROOM_ID, "00000001-0000-4000-8000-000000000000")),
                media_in(
                    key_for(CHATROOM_ID, "00000002-0000-4000-8000-000000000000"),
                    content_type="audio/webm",
                ),
            ],
        )


async def test_two_audios_are_rejected() -> None:
    svc = make_service()
    with pytest.raises(chat_service_module.ValidationError):
        await svc.send_message(
            chatroom_id=CHATROOM_ID,
            sender_id=USER_ID,
            body="",
            media=[
                media_in(
                    key_for(CHATROOM_ID, "00000001-0000-4000-8000-000000000000"),
                    content_type="audio/webm",
                ),
                media_in(
                    key_for(CHATROOM_ID, "00000002-0000-4000-8000-000000000000"),
                    content_type="audio/mp4",
                ),
            ],
        )


async def test_single_audio_message_is_allowed_and_keeps_duration() -> None:
    svc = make_service()
    _, rows, _ = await svc.send_message(
        chatroom_id=CHATROOM_ID,
        sender_id=USER_ID,
        body="",
        media=[media_in(key_for(CHATROOM_ID), content_type="audio/webm", duration=37)],
    )
    assert len(rows) == 1
    assert rows[0].duration == 37


# ── Enqueue contract ──────────────────────────────────────────────────────────


async def test_without_redis_audio_sends_untranscribed(monkeypatch: pytest.MonkeyPatch) -> None:
    """The documented fallback: no Redis → no pending state, no enqueue,
    and — critically — the send itself still succeeds."""
    enqueued: list[str] = []

    async def record(media_id: str) -> None:
        enqueued.append(media_id)

    monkeypatch.setattr(chat_service_module, "enqueue_transcription", record)
    monkeypatch.setattr(
        chat_service_module,
        "get_settings",
        lambda: SimpleNamespace(transcription_enabled=False),
    )
    svc = make_service()
    _, rows, _ = await svc.send_message(
        chatroom_id=CHATROOM_ID,
        sender_id=USER_ID,
        body="",
        media=[media_in(key_for(CHATROOM_ID), content_type="audio/webm")],
    )
    assert rows[0].transcript_status is None
    assert enqueued == []


async def test_with_redis_audio_is_marked_pending_and_enqueued(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    enqueued: list[str] = []

    async def record(media_id: str) -> None:
        enqueued.append(media_id)

    monkeypatch.setattr(chat_service_module, "enqueue_transcription", record)
    monkeypatch.setattr(
        chat_service_module,
        "get_settings",
        lambda: SimpleNamespace(transcription_enabled=True),
    )
    svc = make_service()
    _, rows, _ = await svc.send_message(
        chatroom_id=CHATROOM_ID,
        sender_id=USER_ID,
        body="",
        media=[media_in(key_for(CHATROOM_ID), content_type="audio/webm")],
    )
    assert rows[0].transcript_status == "pending"
    assert enqueued == [rows[0].id]


async def test_images_are_never_marked_pending(monkeypatch: pytest.MonkeyPatch) -> None:
    """Transcription is an audio concept — a photo must not enter the queue
    even with Redis fully configured."""
    enqueued: list[str] = []

    async def record(media_id: str) -> None:
        enqueued.append(media_id)

    monkeypatch.setattr(chat_service_module, "enqueue_transcription", record)
    monkeypatch.setattr(
        chat_service_module,
        "get_settings",
        lambda: SimpleNamespace(transcription_enabled=True),
    )
    svc = make_service()
    _, rows, _ = await svc.send_message(
        chatroom_id=CHATROOM_ID,
        sender_id=USER_ID,
        body="",
        media=[media_in(key_for(CHATROOM_ID))],  # image/jpeg
    )
    assert rows[0].transcript_status is None
    assert enqueued == []


# ── Bridge event parsing ──────────────────────────────────────────────────────


def test_parse_transcript_event_builds_ws_frame() -> None:
    frame = parse_transcript_event(
        '{"chatroom_id": "c1", "message_id": "m1", "media_id": "md1",'
        ' "status": "done", "transcript": "안녕하세요"}'
    )
    assert frame == {
        "type": "transcript",
        "chatroom_id": "c1",
        "message_id": "m1",
        "media_id": "md1",
        "status": "done",
        "transcript": "안녕하세요",
    }


def test_parse_transcript_event_drops_malformed() -> None:
    assert parse_transcript_event("not json") is None
    assert parse_transcript_event('{"chatroom_id": "c1"}') is None  # missing keys
    assert parse_transcript_event("[1,2,3]") is None  # wrong shape


def test_parse_transcript_event_allows_null_transcript() -> None:
    """A failed transcription publishes status=failed with no text."""
    frame = parse_transcript_event(
        '{"chatroom_id": "c1", "message_id": "m1", "media_id": "md1",'
        ' "status": "failed", "transcript": null}'
    )
    assert frame is not None
    assert frame["status"] == "failed"
    assert frame["transcript"] is None


# ── Filename (tech debt #8) ───────────────────────────────────────────────────


async def test_filename_is_persisted_and_served(monkeypatch: pytest.MonkeyPatch) -> None:
    svc = make_service()
    _, rows, _ = await svc.send_message(
        chatroom_id=CHATROOM_ID,
        sender_id=USER_ID,
        body="",
        media=[media_in(key_for(CHATROOM_ID), filename="IMG_4821.jpg")],
    )
    assert rows[0].filename == "IMG_4821.jpg"
    out = ChatService.media_out(rows)
    assert out[0].filename == "IMG_4821.jpg"


async def test_download_prefers_stored_filename(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.models.message_media import MessageMedia
    from tests.test_chat_media import FakeMediaLookupRepo

    captured: dict[str, str | None] = {}

    def fake_presign_get(object_key: str, *, download_filename: str | None = None) -> str:
        captured["download_filename"] = download_filename
        return "https://signed.example/x"

    monkeypatch.setattr(chat_service_module.storage, "presign_get", fake_presign_get)

    svc = ChatService(FakeDb())
    media = MessageMedia(
        id="media-1",
        message_id="msg-1",
        type="image/jpeg",
        object_key=key_for(CHATROOM_ID),
        filename="여행사진.jpg",
    )
    svc._media_repo = FakeMediaLookupRepo(media, CHATROOM_ID)  # type: ignore[attr-defined]
    await svc.presign_media_download(CHATROOM_ID, "media-1")
    assert captured["download_filename"] == "여행사진.jpg"


async def test_download_falls_back_to_synthesised_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.models.message_media import MessageMedia
    from tests.test_chat_media import FakeMediaLookupRepo

    captured: dict[str, str | None] = {}

    def fake_presign_get(object_key: str, *, download_filename: str | None = None) -> str:
        captured["download_filename"] = download_filename
        return "https://signed.example/x"

    monkeypatch.setattr(chat_service_module.storage, "presign_get", fake_presign_get)

    svc = ChatService(FakeDb())
    media = MessageMedia(
        id="media-1",
        message_id="msg-1",
        type="audio/mp4",
        object_key=key_for(CHATROOM_ID),
        filename=None,
    )
    svc._media_repo = FakeMediaLookupRepo(media, CHATROOM_ID)  # type: ignore[attr-defined]
    await svc.presign_media_download(CHATROOM_ID, "media-1")
    assert captured["download_filename"] == "jamye-media-1.m4a"
