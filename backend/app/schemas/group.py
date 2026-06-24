"""Group and membership schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class GroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)


class GroupOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    owner_id: str
    max_members: int
    member_count: int = 0
    created_at: datetime
    main_chatroom_id: str | None = None


class MembershipOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    group_id: str
    user_id: str
    role: str
    joined_at: datetime


class GroupMemberOut(BaseModel):
    """A group member enriched with their display profile (nickname + avatar)."""

    user_id: str
    nickname: str
    avatar_url: str | None = None
    role: str
    joined_at: datetime
