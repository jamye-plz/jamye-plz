"""Topic, TopicMedia and TopicTag schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


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


class MediaPresignRequest(BaseModel):
    content_type: str = Field(min_length=1, max_length=64)
    byte_size: int = Field(ge=1)


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
