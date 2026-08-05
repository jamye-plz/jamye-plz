"""Chat / message schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.storage import AUDIO_MIME_TYPES, CHAT_MEDIA_MIME_TYPES, max_bytes_for

# ── Media ─────────────────────────────────────────────────────────────────────


def _check_chat_media_content_type(v: str) -> str:
    if v not in CHAT_MEDIA_MIME_TYPES:
        allowed = ", ".join(sorted(CHAT_MEDIA_MIME_TYPES))
        raise ValueError(f"content_type must be one of: {allowed}")
    return v


class ChatMediaPresignRequest(BaseModel):
    content_type: str = Field(min_length=1, max_length=64)
    byte_size: int = Field(ge=1)

    @field_validator("content_type")
    @classmethod
    def validate_content_type(cls, v: str) -> str:
        return _check_chat_media_content_type(v)

    # The cap depends on content_type, so it can only be checked once both
    # fields are bound. `model_validator(mode="after")` keeps the failure a
    # pydantic ValidationError → FastAPI 422 (raising from model_post_init
    # would escape as a bare ValueError and surface as a 500).
    @model_validator(mode="after")
    def validate_byte_size_for_kind(self) -> "ChatMediaPresignRequest":
        cap = max_bytes_for(self.content_type)
        if self.byte_size > cap:
            raise ValueError(f"byte_size must not exceed {cap} bytes for {self.content_type}")
        return self


class ChatMediaPresignOut(BaseModel):
    object_key: str
    upload_url: str
    expires_in: int


class MessageMediaIn(BaseModel):
    """One attachment as claimed by the client on the WS send_message frame.

    Every field here is client-supplied and therefore untrusted: the service
    re-validates content_type/byte_size against the allowlist and the per-kind
    cap, and checks object_key against the chatroom's prefix (BOLA guard).
    """

    object_key: str = Field(min_length=1, max_length=512)
    content_type: str = Field(min_length=1, max_length=64)
    width: int | None = Field(None, ge=1)
    height: int | None = Field(None, ge=1)
    byte_size: int | None = Field(None, ge=1)
    duration: int | None = Field(None, ge=0)
    # Original client-side name, restored on download (tech debt #8).
    filename: str | None = Field(None, max_length=255)

    @field_validator("content_type")
    @classmethod
    def validate_content_type(cls, v: str) -> str:
        return _check_chat_media_content_type(v)

    @model_validator(mode="after")
    def validate_byte_size_for_kind(self) -> "MessageMediaIn":
        # Audio must declare its size: the row feeds a CPU-bound worker whose
        # budget depends on it, so "omitted" cannot mean "unchecked". (For
        # images/video the browser is the consumer and the presign signature
        # already bounds the actual upload.) The worker additionally verifies
        # the REAL object size before downloading — this check is UX, that one
        # is the enforcement.
        if self.content_type in AUDIO_MIME_TYPES and self.byte_size is None:
            raise ValueError("byte_size is required for audio attachments")
        if self.byte_size is not None:
            cap = max_bytes_for(self.content_type)
            if self.byte_size > cap:
                raise ValueError(f"byte_size must not exceed {cap} bytes for {self.content_type}")
        return self


class MessageMediaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    url: str
    content_type: str
    width: int | None = None
    height: int | None = None
    byte_size: int | None = None
    duration: int | None = None
    filename: str | None = None
    # Async STT (M4a): pending | done | failed; None = not applicable/disabled.
    transcript: str | None = None
    transcript_status: str | None = None


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    chatroom_id: str
    sender_id: str | None = None
    sender_nickname: str | None = None
    sender_avatar_url: str | None = None
    client_msg_id: str | None = None
    body: str
    type: str
    created_at: datetime
    media: list[MessageMediaOut] = Field(default_factory=list)


class MessagePage(BaseModel):
    items: list[MessageOut]
    next_cursor: str | None = None


class ChatroomOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    group_id: str
    type: str
    topic_id: str | None = None
    created_at: datetime
