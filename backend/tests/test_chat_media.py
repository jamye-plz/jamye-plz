"""Chat media attachment tests (M3).

Covers the three things that can actually hurt us:
  1. the BOLA guard on object_key (cross-chatroom object theft),
  2. server-side re-validation of client-claimed MIME/size,
  3. the relaxed empty-body rule (media-only messages allowed, empty ones not).

Service-level tests against fakes — no DB engine, same style as
test_chat_service.py.
"""

import pytest
from pydantic import ValidationError as PydanticValidationError

from app.core import storage
from app.core.exceptions import NotFoundError, ValidationError
from app.models.message import Message
from app.models.message_media import MessageMedia
from app.schemas.chat import ChatMediaPresignRequest, MessageMediaIn
from app.services.chat_service import ChatService

CHATROOM_ID = "chatroom-1"
OTHER_CHATROOM_ID = "chatroom-2"
USER_ID = "user-1"


class FakeDb:
    def add(self, obj: object) -> None:
        pass

    def add_all(self, objs: object) -> None:
        pass

    async def commit(self) -> None:
        pass

    async def flush(self) -> None:
        pass

    async def refresh(self, obj: object) -> None:
        pass


class FakeMessageRepo:
    def __init__(self) -> None:
        self.created: list[Message] = []

    async def get_by_client_msg_id(self, sender_id: str, client_msg_id: str) -> Message | None:
        return None

    async def create(
        self,
        chatroom_id: str,
        body: str,
        sender_id: str | None = None,
        client_msg_id: str | None = None,
        type: str = "user",
    ) -> Message:
        msg = Message(
            id=f"msg-{len(self.created)}",
            chatroom_id=chatroom_id,
            body=body,
            sender_id=sender_id,
            client_msg_id=client_msg_id,
            type=type,
        )
        self.created.append(msg)
        return msg


class FakeMediaRepo:
    def __init__(self) -> None:
        self.created: list[dict[str, object]] = []

    async def create_many(
        self, message_id: str, items: list[dict[str, object]]
    ) -> list[MessageMedia]:
        self.created.extend(items)
        return [
            MessageMedia(
                id=f"media-{i}",
                message_id=message_id,
                type=str(item["content_type"]),
                object_key=str(item["object_key"]),
                width=item.get("width"),  # type: ignore[arg-type]
                height=item.get("height"),  # type: ignore[arg-type]
                byte_size=item.get("byte_size"),  # type: ignore[arg-type]
                duration=item.get("duration"),  # type: ignore[arg-type]
                filename=item.get("filename"),  # type: ignore[arg-type]
            )
            for i, item in enumerate(items)
        ]


def make_service() -> ChatService:
    svc = ChatService(FakeDb())
    svc._message_repo = FakeMessageRepo()  # type: ignore[attr-defined]
    svc._media_repo = FakeMediaRepo()  # type: ignore[attr-defined]
    return svc


def media_in(object_key: str, content_type: str = "image/jpeg", **kw: object) -> MessageMediaIn:
    return MessageMediaIn(object_key=object_key, content_type=content_type, **kw)  # type: ignore[arg-type]


def key_for(chatroom_id: str, name: str = "3b1e0000-0000-4000-8000-000000000000") -> str:
    return f"chat/{chatroom_id}/{name}"


# ── BOLA guard ────────────────────────────────────────────────────────────────
# The attack: a member of group B presigns nothing, but reuses an object_key
# they observed from group A. Without the guard, their own message's presigned
# GET would hand their groupmates read access to group A's private object.


def test_object_key_from_another_chatroom_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ChatService.validate_object_key_for_chatroom(CHATROOM_ID, key_for(OTHER_CHATROOM_ID))


def test_object_key_for_topic_namespace_is_rejected() -> None:
    # A topic media key must not be attachable to a chat message either.
    with pytest.raises(ValidationError):
        ChatService.validate_object_key_for_chatroom(CHATROOM_ID, "topics/topic-1/abc")


def test_object_key_with_extra_path_segment_is_rejected() -> None:
    # `chat/{cid}/../other/obj`-style traversal into a sibling prefix.
    with pytest.raises(ValidationError):
        ChatService.validate_object_key_for_chatroom(CHATROOM_ID, f"chat/{CHATROOM_ID}/a/b")


def test_object_key_with_empty_suffix_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ChatService.validate_object_key_for_chatroom(CHATROOM_ID, f"chat/{CHATROOM_ID}/")


def test_object_key_prefix_confusion_is_rejected() -> None:
    # `chat/chatroom-10/...` must not pass the guard for `chatroom-1`.
    with pytest.raises(ValidationError):
        ChatService.validate_object_key_for_chatroom(CHATROOM_ID, "chat/chatroom-10/obj")


def test_valid_object_key_passes() -> None:
    ChatService.validate_object_key_for_chatroom(CHATROOM_ID, key_for(CHATROOM_ID))


async def test_send_message_rejects_foreign_object_key() -> None:
    svc = make_service()
    with pytest.raises(ValidationError):
        await svc.send_message(
            chatroom_id=CHATROOM_ID,
            sender_id=USER_ID,
            body="",
            media=[media_in(key_for(OTHER_CHATROOM_ID))],
        )


# ── Body / media presence ─────────────────────────────────────────────────────


async def test_message_with_neither_body_nor_media_is_rejected() -> None:
    svc = make_service()
    with pytest.raises(ValidationError):
        await svc.send_message(chatroom_id=CHATROOM_ID, sender_id=USER_ID, body="")


async def test_media_only_message_is_allowed() -> None:
    svc = make_service()
    message, rows, is_new = await svc.send_message(
        chatroom_id=CHATROOM_ID,
        sender_id=USER_ID,
        body="",
        media=[media_in(key_for(CHATROOM_ID))],
    )
    assert is_new
    assert message.body == ""
    assert len(rows) == 1
    assert rows[0].type == "image/jpeg"


async def test_text_only_message_still_works() -> None:
    svc = make_service()
    message, rows, _ = await svc.send_message(
        chatroom_id=CHATROOM_ID, sender_id=USER_ID, body="안녕"
    )
    assert message.body == "안녕"
    assert rows == []


# ── Count / duplicate limits ──────────────────────────────────────────────────


async def test_more_than_max_attachments_is_rejected() -> None:
    svc = make_service()
    too_many = [
        media_in(key_for(CHATROOM_ID, f"0000000{i}-0000-4000-8000-000000000000"))
        for i in range(storage.MAX_MEDIA_PER_MESSAGE + 1)
    ]
    with pytest.raises(ValidationError):
        await svc.send_message(chatroom_id=CHATROOM_ID, sender_id=USER_ID, body="", media=too_many)


async def test_max_attachments_exactly_is_allowed() -> None:
    svc = make_service()
    exactly = [
        media_in(key_for(CHATROOM_ID, f"0000000{i}-0000-4000-8000-000000000000"))
        for i in range(storage.MAX_MEDIA_PER_MESSAGE)
    ]
    _, rows, _ = await svc.send_message(
        chatroom_id=CHATROOM_ID, sender_id=USER_ID, body="", media=exactly
    )
    assert len(rows) == storage.MAX_MEDIA_PER_MESSAGE


async def test_duplicate_object_key_is_rejected() -> None:
    svc = make_service()
    same = key_for(CHATROOM_ID)
    with pytest.raises(ValidationError):
        await svc.send_message(
            chatroom_id=CHATROOM_ID,
            sender_id=USER_ID,
            body="",
            media=[media_in(same), media_in(same)],
        )


# ── MIME / size re-validation ─────────────────────────────────────────────────
# The WS frame is client-supplied: a client can presign a small jpeg and then
# claim anything on send. These run at the schema layer, before the service.


def test_disallowed_mime_is_rejected() -> None:
    for bad in ("application/pdf", "image/heic", "video/quicktime", "text/html"):
        with pytest.raises(PydanticValidationError):
            MessageMediaIn(object_key=key_for(CHATROOM_ID), content_type=bad)


def test_image_over_cap_is_rejected() -> None:
    with pytest.raises(PydanticValidationError):
        MessageMediaIn(
            object_key=key_for(CHATROOM_ID),
            content_type="image/jpeg",
            byte_size=storage.MAX_IMAGE_BYTES + 1,
        )


def test_video_over_cap_is_rejected() -> None:
    with pytest.raises(PydanticValidationError):
        MessageMediaIn(
            object_key=key_for(CHATROOM_ID),
            content_type="video/mp4",
            byte_size=storage.MAX_VIDEO_BYTES + 1,
        )


def test_video_between_image_and_video_cap_is_allowed() -> None:
    # Guards against a regression where the image cap is applied to video.
    m = MessageMediaIn(
        object_key=key_for(CHATROOM_ID),
        content_type="video/mp4",
        byte_size=storage.MAX_IMAGE_BYTES + 1,
    )
    assert m.byte_size == storage.MAX_IMAGE_BYTES + 1


def test_video_cap_stays_under_cloudflare_limit() -> None:
    # The browser PUTs through a Cloudflare tunnel whose free-plan request body
    # limit is 100 MB. If someone raises this cap, the upload starts failing at
    # the edge with an error the app cannot explain.
    assert storage.MAX_VIDEO_BYTES <= 100 * 1000 * 1000


async def test_duration_is_dropped_for_images() -> None:
    svc = make_service()
    _, rows, _ = await svc.send_message(
        chatroom_id=CHATROOM_ID,
        sender_id=USER_ID,
        body="",
        media=[media_in(key_for(CHATROOM_ID), content_type="image/jpeg", duration=42)],
    )
    assert rows[0].duration is None


async def test_duration_is_kept_for_video() -> None:
    svc = make_service()
    _, rows, _ = await svc.send_message(
        chatroom_id=CHATROOM_ID,
        sender_id=USER_ID,
        body="",
        media=[media_in(key_for(CHATROOM_ID), content_type="video/mp4", duration=42)],
    )
    assert rows[0].duration == 42


# ── Presign request validation ────────────────────────────────────────────────


def test_presign_rejects_disallowed_mime() -> None:
    with pytest.raises(PydanticValidationError):
        ChatMediaPresignRequest(content_type="application/zip", byte_size=1)


def test_presign_rejects_oversized_image() -> None:
    with pytest.raises(PydanticValidationError):
        ChatMediaPresignRequest(content_type="image/png", byte_size=storage.MAX_IMAGE_BYTES + 1)


def test_presign_accepts_video_up_to_video_cap() -> None:
    req = ChatMediaPresignRequest(content_type="video/mp4", byte_size=storage.MAX_VIDEO_BYTES)
    assert req.byte_size == storage.MAX_VIDEO_BYTES


def test_presign_rejects_zero_bytes() -> None:
    with pytest.raises(PydanticValidationError):
        ChatMediaPresignRequest(content_type="image/jpeg", byte_size=0)


# ── media_out ─────────────────────────────────────────────────────────────────


# ── Download (IDOR guard + filename) ──────────────────────────────────────────


class FakeMediaLookupRepo:
    """Mirrors get_in_chatroom's join: media is only visible in its own room."""

    def __init__(self, media: MessageMedia, chatroom_id: str) -> None:
        self.media = media
        self.chatroom_id = chatroom_id

    async def get_in_chatroom(self, media_id: str, chatroom_id: str) -> MessageMedia | None:
        if media_id == self.media.id and chatroom_id == self.chatroom_id:
            return self.media
        return None


def make_download_service(chatroom_id: str = CHATROOM_ID) -> ChatService:
    svc = ChatService(FakeDb())
    media = MessageMedia(
        id="media-1",
        message_id="msg-1",
        type="image/jpeg",
        object_key=key_for(chatroom_id),
    )
    svc._media_repo = FakeMediaLookupRepo(media, chatroom_id)  # type: ignore[attr-defined]
    return svc


async def test_download_rejects_media_from_another_chatroom() -> None:
    # The attack: guess a media id and ask for it from a room you DO belong to.
    svc = make_download_service()
    with pytest.raises(NotFoundError):
        await svc.presign_media_download(OTHER_CHATROOM_ID, "media-1")


async def test_download_rejects_unknown_media_id() -> None:
    svc = make_download_service()
    with pytest.raises(NotFoundError):
        await svc.presign_media_download(CHATROOM_ID, "media-does-not-exist")


async def test_download_returns_a_url_for_own_chatroom() -> None:
    svc = make_download_service()
    url = await svc.presign_media_download(CHATROOM_ID, "media-1")
    assert url


async def test_refresh_url_rejects_media_from_another_chatroom() -> None:
    svc = make_download_service()
    with pytest.raises(NotFoundError):
        await svc.presign_media_view(OTHER_CHATROOM_ID, "media-1")


async def test_refresh_url_returns_media_with_a_url() -> None:
    svc = make_download_service()
    out = await svc.presign_media_view(CHATROOM_ID, "media-1")
    assert out.id == "media-1"
    assert out.url


# ── Attachment order ──────────────────────────────────────────────────────────
# created_at ties across a message's attachments (one transaction, stable
# now()), so without a stored ordinal the tiebreak is a random uuid and
# reloaded history reshuffles what the sender picked.


async def test_attachment_positions_follow_pick_order() -> None:
    svc = ChatService(FakeDb())
    svc._message_repo = FakeMessageRepo()  # type: ignore[attr-defined]
    captured: list[dict[str, object]] = []

    class RecordingMediaRepo:
        async def create_many(
            self, message_id: str, items: list[dict[str, object]]
        ) -> list[MessageMedia]:
            captured.extend(items)
            return [
                MessageMedia(
                    id=f"media-{i}",
                    message_id=message_id,
                    type=str(item["content_type"]),
                    object_key=str(item["object_key"]),
                    position=i,
                )
                for i, item in enumerate(items)
            ]

    svc._media_repo = RecordingMediaRepo()  # type: ignore[attr-defined]
    keys = [key_for(CHATROOM_ID, f"0000000{i}-0000-4000-8000-000000000000") for i in range(3)]
    _, rows, _ = await svc.send_message(
        chatroom_id=CHATROOM_ID,
        sender_id=USER_ID,
        body="",
        media=[media_in(k) for k in keys],
    )
    # The service must hand the repo the items in the order the sender picked;
    # the repo stamps position from that order.
    assert [str(item["object_key"]) for item in captured] == keys
    assert [r.position for r in rows] == [0, 1, 2]


def test_download_filename_uses_extension_from_mime() -> None:
    assert storage.download_filename_for("abc", "image/jpeg").endswith(".jpg")
    assert storage.download_filename_for("abc", "video/mp4").endswith(".mp4")
    # Unknown type must still produce a safe, extension-bearing name.
    assert storage.download_filename_for("abc", "application/x-evil").endswith(".bin")


def test_download_filename_has_no_path_or_quote_characters() -> None:
    name = storage.download_filename_for("../../etc/passwd", "image/png")
    assert '"' not in name


def test_media_out_attaches_a_url_per_row() -> None:
    rows = [
        MessageMedia(
            id="media-1",
            message_id="msg-1",
            type="image/jpeg",
            object_key=key_for(CHATROOM_ID),
            width=100,
            height=200,
            byte_size=1234,
            duration=None,
        )
    ]
    out = ChatService.media_out(rows)
    assert len(out) == 1
    assert out[0].id == "media-1"
    assert out[0].content_type == "image/jpeg"
    assert out[0].width == 100
    assert out[0].url  # a URL was issued (fallback or presigned)
