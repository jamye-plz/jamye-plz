"""Topic, TopicMedia and TopicTag schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.storage import IMAGE_MIME_TYPES, MAX_IMAGE_BYTES


# ── Topic ──────────────────────────────────────────────────────────────────────


class TopicCreate(BaseModel):
    title: str = Field(min_length=1, max_length=256)


class TopicPatch(BaseModel):
    body: str | None = Field(None, min_length=1)


class TopicTagOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    tag: str
    source: str


class TopicMediaOut(BaseModel):
    id: str
    object_key: str
    url: str
    width: int | None = None
    height: int | None = None
    content_type: str


class TopicOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    group_id: str
    author_id: str
    author_nickname: str = ""
    author_avatar_url: str | None = None
    title: str
    body: str | None = None
    status: str
    tags: list[TopicTagOut] = []
    media: list[TopicMediaOut] = []
    chatroom_id: str | None = None
    unread: bool = False
    created_at: datetime
    updated_at: datetime


class TopicPage(BaseModel):
    items: list[TopicOut]
    next_cursor: str | None = None


class TopicDatesOut(BaseModel):
    dates: list[str]
    today: str


# ── Media ─────────────────────────────────────────────────────────────────────


def _check_image_content_type(v: str) -> str:
    if v not in IMAGE_MIME_TYPES:
        allowed = ", ".join(sorted(IMAGE_MIME_TYPES))
        raise ValueError(f"content_type must be one of: {allowed}")
    return v


def _check_image_byte_size(v: int) -> int:
    if v > MAX_IMAGE_BYTES:
        raise ValueError(f"byte_size must not exceed {MAX_IMAGE_BYTES} bytes")
    return v


class MediaPresignRequest(BaseModel):
    content_type: str = Field(min_length=1, max_length=64)
    byte_size: int = Field(ge=1)

    @field_validator("content_type")
    @classmethod
    def validate_content_type(cls, v: str) -> str:
        return _check_image_content_type(v)

    @field_validator("byte_size")
    @classmethod
    def validate_byte_size(cls, v: int) -> int:
        return _check_image_byte_size(v)


class MediaPresignOut(BaseModel):
    object_key: str
    upload_url: str
    expires_in: int


class MediaConfirmRequest(BaseModel):
    object_key: str = Field(min_length=1, max_length=512)
    content_type: str = Field(min_length=1, max_length=64)
    width: int | None = Field(None, ge=1)
    height: int | None = Field(None, ge=1)
    byte_size: int | None = Field(None, ge=1)

    @field_validator("content_type")
    @classmethod
    def validate_content_type(cls, v: str) -> str:
        return _check_image_content_type(v)

    @field_validator("byte_size")
    @classmethod
    def validate_byte_size(cls, v: int | None) -> int | None:
        if v is None:
            return v
        return _check_image_byte_size(v)


class MediaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    topic_id: str
    type: str
    object_key: str
    width: int | None = None
    height: int | None = None
    byte_size: int | None = None
    created_at: datetime


# ── Tags ──────────────────────────────────────────────────────────────────────


class TagItem(BaseModel):
    tag: str = Field(min_length=1, max_length=64)
    source: str = Field(pattern="^(ai|user)$")
    confidence: float | None = Field(None, ge=0.0, le=1.0)


class TagsSync(BaseModel):
    tags: list[TagItem]


class TagOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    topic_id: str
    tag: str
    source: str
    confidence: float | None = None
