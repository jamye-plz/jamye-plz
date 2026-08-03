"""Unit tests for ChatService.require_member_access (WS join / send_message
authorization gate).

Pure service-level tests against fake in-memory repositories — no DB engine.
"""

from datetime import datetime, timezone

import pytest

from app.core.exceptions import ForbiddenError, NotFoundError
from app.models.chatroom import Chatroom
from app.models.group import Group
from app.models.membership import Membership
from app.services.chat_service import ChatService

GROUP_ID = "group-1"
CHATROOM_ID = "chatroom-1"
USER_ID = "user-1"


class FakeDb:
    """Stands in for AsyncSession: no-op transaction control."""

    def add(self, obj: object) -> None:
        pass

    async def commit(self) -> None:
        pass

    async def refresh(self, obj: object) -> None:
        pass


class FakeChatroomRepo:
    def __init__(self, chatroom: Chatroom | None) -> None:
        self.chatroom = chatroom

    async def get_by_id(self, chatroom_id: str) -> Chatroom | None:
        if self.chatroom is not None and self.chatroom.id == chatroom_id:
            return self.chatroom
        return None


class FakeGroupRepo:
    """Mirrors GroupRepository.get_by_id's Group.deleted_at.is_(None) filter."""

    def __init__(self, group: Group | None) -> None:
        self.group = group

    async def get_by_id(self, group_id: str) -> Group | None:
        if self.group is None or self.group.id != group_id or self.group.deleted_at is not None:
            return None
        return self.group


class FakeMembershipRepo:
    def __init__(self, member_ids: set[str]) -> None:
        self.member_ids = member_ids

    async def get(self, group_id: str, user_id: str) -> Membership | None:
        if user_id in self.member_ids:
            return Membership(id=f"m-{user_id}", group_id=group_id, user_id=user_id, role="member")
        return None


def make_group(deleted: bool = False) -> Group:
    return Group(
        id=GROUP_ID,
        name="Test Group",
        owner_id=USER_ID,
        max_members=12,
        deleted_at=datetime.now(timezone.utc) if deleted else None,
    )


def make_chat_service(group: Group | None, member_ids: set[str]) -> ChatService:
    svc = ChatService(FakeDb())
    chatroom = Chatroom(id=CHATROOM_ID, group_id=GROUP_ID, type="main", topic_id=None)
    svc._chatroom_repo = FakeChatroomRepo(chatroom)  # type: ignore[attr-defined]
    svc._group_repo = FakeGroupRepo(group)  # type: ignore[attr-defined]
    svc._membership_repo = FakeMembershipRepo(member_ids)  # type: ignore[attr-defined]
    return svc


# ── QA regression: WS join/send_message bypass GroupService, so a
# soft-deleted group's chatroom must still 404 here (not stay reachable
# just because the membership row is untouched by soft-delete). ─────────────


async def test_require_member_access_on_deleted_group_is_not_found() -> None:
    svc = make_chat_service(make_group(deleted=True), {USER_ID})
    with pytest.raises(NotFoundError):
        await svc.require_member_access(CHATROOM_ID, USER_ID)


async def test_require_member_access_on_missing_group_is_not_found() -> None:
    svc = make_chat_service(None, {USER_ID})
    with pytest.raises(NotFoundError):
        await svc.require_member_access(CHATROOM_ID, USER_ID)


async def test_require_member_access_missing_chatroom_is_not_found() -> None:
    svc = ChatService(FakeDb())
    svc._chatroom_repo = FakeChatroomRepo(None)  # type: ignore[attr-defined]
    svc._group_repo = FakeGroupRepo(make_group())  # type: ignore[attr-defined]
    svc._membership_repo = FakeMembershipRepo({USER_ID})  # type: ignore[attr-defined]
    with pytest.raises(NotFoundError):
        await svc.require_member_access(CHATROOM_ID, USER_ID)


async def test_require_member_access_non_member_is_forbidden() -> None:
    svc = make_chat_service(make_group(), set())
    with pytest.raises(ForbiddenError):
        await svc.require_member_access(CHATROOM_ID, USER_ID)


async def test_require_member_access_member_on_live_group_succeeds() -> None:
    svc = make_chat_service(make_group(), {USER_ID})
    chatroom = await svc.require_member_access(CHATROOM_ID, USER_ID)
    assert chatroom.id == CHATROOM_ID
