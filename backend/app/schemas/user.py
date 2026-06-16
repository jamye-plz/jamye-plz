"""User schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    provider: str
    nickname: str
    avatar_url: str | None = None
    created_at: datetime


class UserPatch(BaseModel):
    nickname: str | None = Field(None, min_length=1, max_length=64)
    avatar_url: str | None = Field(None, max_length=512)
