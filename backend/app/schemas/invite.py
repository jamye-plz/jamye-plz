"""Invite schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class InviteCreate(BaseModel):
    expires_at: datetime | None = None
    max_uses: int | None = Field(None, ge=1)


class InviteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    group_id: str
    code: str
    created_by: str
    expires_at: datetime | None = None
    max_uses: int | None = None
    used_count: int
    created_at: datetime
