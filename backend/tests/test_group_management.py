"""Unit tests for GroupService group-management methods (M2).

These are pure service-level tests against fake in-memory repositories — no
DB engine, no HTTP test client. Fakes implement only the methods
GroupService actually calls, so a signature drift in the real repository
surfaces as an AttributeError here.
"""

from datetime import datetime, timezone

import pytest

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.models.group import Group
from app.models.membership import Membership
from app.services.group_service import GroupService

GROUP_ID = "group-1"
OWNER_ID = "user-owner"
MEMBER_ID = "user-member"
OTHER_ID = "user-other"


class FakeDb:
    """Stands in for AsyncSession: no-op transaction control, tracks add()."""

    def __init__(self) -> None:
        self.added: list[object] = []
        self.commits = 0

    def add(self, obj: object) -> None:
        self.added.append(obj)

    async def commit(self) -> None:
        self.commits += 1

    async def refresh(self, obj: object) -> None:
        pass


class FakeGroupRepo:
    def __init__(self, groups: dict[str, Group]) -> None:
        self.groups = groups

    async def get_by_id(self, group_id: str) -> Group | None:
        group = self.groups.get(group_id)
        if group is None or group.deleted_at is not None:
            return None
        return group

    async def get_by_id_for_update(self, group_id: str) -> Group | None:
        # No real row lock in the fake; behaves like a live-group read.
        return await self.get_by_id(group_id)

    async def update_name(self, group_id: str, name: str) -> Group | None:
        group = await self.get_by_id(group_id)
        if group is None:
            return None
        group.name = name
        return group

    async def soft_delete(self, group_id: str) -> None:
        group = self.groups.get(group_id)
        if group is None:
            return
        group.deleted_at = datetime.now(timezone.utc)

    async def member_count(self, group_id: str) -> int:
        raise NotImplementedError("not used by these tests")


class FakeMembershipRepo:
    def __init__(self, memberships: dict[tuple[str, str], Membership]) -> None:
        self.memberships = memberships

    async def get(self, group_id: str, user_id: str) -> Membership | None:
        return self.memberships.get((group_id, user_id))

    async def create(self, group_id: str, user_id: str, role: str = "member") -> Membership:
        membership = Membership(
            id=f"m-{group_id}-{user_id}", group_id=group_id, user_id=user_id, role=role
        )
        self.memberships[(group_id, user_id)] = membership
        return membership

    async def list_by_group(self, group_id: str) -> list[Membership]:
        return [m for (g, _u), m in self.memberships.items() if g == group_id]

    async def delete(self, membership: Membership) -> None:
        self.memberships.pop((membership.group_id, membership.user_id), None)

    async def update_role(self, membership: Membership, role: str) -> Membership:
        membership.role = role
        return membership


def make_group(deleted: bool = False) -> Group:
    return Group(
        id=GROUP_ID,
        name="Test Group",
        owner_id=OWNER_ID,
        max_members=12,
        deleted_at=datetime.now(timezone.utc) if deleted else None,
    )


def make_membership(user_id: str, role: str) -> Membership:
    return Membership(id=f"m-{user_id}", group_id=GROUP_ID, user_id=user_id, role=role)


class FakeChatroom:
    def __init__(self, id: str) -> None:
        self.id = id


class FakeChatroomRepo:
    def __init__(self, chatroom_ids: list[str]) -> None:
        self.chatroom_ids = chatroom_ids

    async def list_by_group(self, group_id: str) -> list[FakeChatroom]:
        return [FakeChatroom(cid) for cid in self.chatroom_ids]


def make_service(
    group: Group | None,
    memberships: dict[tuple[str, str], Membership],
    chatroom_ids: list[str] | None = None,
) -> tuple[GroupService, FakeDb]:
    db = FakeDb()
    svc = GroupService(db)
    groups = {group.id: group} if group is not None else {}
    svc._group_repo = FakeGroupRepo(groups)  # type: ignore[attr-defined]
    svc._membership_repo = FakeMembershipRepo(memberships)  # type: ignore[attr-defined]
    svc._chatroom_repo = FakeChatroomRepo(chatroom_ids or [])  # type: ignore[attr-defined]
    return svc, db


def owner_and_member() -> dict[tuple[str, str], Membership]:
    return {
        (GROUP_ID, OWNER_ID): make_membership(OWNER_ID, "owner"),
        (GROUP_ID, MEMBER_ID): make_membership(MEMBER_ID, "member"),
    }


# ── Non-owner 403 on rename / delete / remove / transfer ───────────────────


async def test_rename_by_non_owner_is_forbidden() -> None:
    svc, _db = make_service(make_group(), owner_and_member())
    with pytest.raises(ForbiddenError):
        await svc.update_group_name(GROUP_ID, MEMBER_ID, "New Name")


async def test_delete_by_non_owner_is_forbidden() -> None:
    svc, _db = make_service(make_group(), owner_and_member())
    with pytest.raises(ForbiddenError):
        await svc.soft_delete_group(GROUP_ID, MEMBER_ID)


async def test_remove_member_by_non_owner_is_forbidden() -> None:
    memberships = owner_and_member()
    memberships[(GROUP_ID, OTHER_ID)] = make_membership(OTHER_ID, "member")
    svc, _db = make_service(make_group(), memberships)
    with pytest.raises(ForbiddenError):
        await svc.remove_member(GROUP_ID, MEMBER_ID, OTHER_ID)


async def test_transfer_ownership_by_non_owner_is_forbidden() -> None:
    svc, _db = make_service(make_group(), owner_and_member())
    with pytest.raises(ForbiddenError):
        await svc.transfer_ownership(GROUP_ID, MEMBER_ID, OWNER_ID)


# ── Owner leave is blocked (409) ────────────────────────────────────────────


async def test_owner_leave_is_conflict() -> None:
    svc, db = make_service(make_group(), owner_and_member())
    with pytest.raises(ConflictError):
        await svc.leave_group(GROUP_ID, OWNER_ID)
    assert db.commits == 0


async def test_member_leave_succeeds() -> None:
    memberships = owner_and_member()
    svc, db = make_service(make_group(), memberships)
    await svc.leave_group(GROUP_ID, MEMBER_ID)
    assert (GROUP_ID, MEMBER_ID) not in memberships
    assert db.commits == 1


# ── Transfer ownership swaps owner_id + both roles ──────────────────────────


async def test_transfer_ownership_swaps_owner_id_and_roles() -> None:
    group = make_group()
    memberships = owner_and_member()
    svc, db = make_service(group, memberships)

    result = await svc.transfer_ownership(GROUP_ID, OWNER_ID, MEMBER_ID)

    assert result.owner_id == MEMBER_ID
    assert memberships[(GROUP_ID, MEMBER_ID)].role == "owner"
    assert memberships[(GROUP_ID, OWNER_ID)].role == "member"
    assert db.commits == 1


async def test_transfer_ownership_target_already_owner_is_conflict() -> None:
    svc, _db = make_service(make_group(), owner_and_member())
    with pytest.raises(ConflictError):
        await svc.transfer_ownership(GROUP_ID, OWNER_ID, OWNER_ID)


# ── Remove of non-member is 404 ─────────────────────────────────────────────


async def test_remove_non_member_is_not_found() -> None:
    svc, _db = make_service(make_group(), owner_and_member())
    with pytest.raises(NotFoundError):
        await svc.remove_member(GROUP_ID, OWNER_ID, OTHER_ID)


# ── Self-remove by owner → conflict (must transfer first) ──────────────────


async def test_owner_self_remove_is_conflict() -> None:
    svc, db = make_service(make_group(), owner_and_member())
    with pytest.raises(ConflictError):
        await svc.remove_member(GROUP_ID, OWNER_ID, OWNER_ID)
    assert db.commits == 0


async def test_owner_removes_member_succeeds() -> None:
    memberships = owner_and_member()
    svc, db = make_service(make_group(), memberships)
    await svc.remove_member(GROUP_ID, OWNER_ID, MEMBER_ID)
    assert (GROUP_ID, MEMBER_ID) not in memberships
    assert db.commits == 1


async def test_rename_by_owner_succeeds() -> None:
    group = make_group()
    svc, db = make_service(group, owner_and_member())
    result = await svc.update_group_name(GROUP_ID, OWNER_ID, "새 이름")
    assert result.name == "새 이름"
    assert db.commits == 1


async def test_delete_by_owner_succeeds() -> None:
    group = make_group()
    svc, db = make_service(group, owner_and_member())
    await svc.soft_delete_group(GROUP_ID, OWNER_ID)
    assert group.deleted_at is not None
    assert db.commits == 1


# ── Soft-deleted group is invisible via get_group_or_404 ───────────────────


async def test_soft_deleted_group_is_not_found() -> None:
    svc, _db = make_service(make_group(deleted=True), owner_and_member())
    with pytest.raises(NotFoundError):
        await svc.get_group_or_404(GROUP_ID)


async def test_missing_group_is_not_found() -> None:
    svc, _db = make_service(None, {})
    with pytest.raises(NotFoundError):
        await svc.get_group_or_404(GROUP_ID)


async def test_mutation_on_soft_deleted_group_is_not_found() -> None:
    svc, _db = make_service(make_group(deleted=True), owner_and_member())
    with pytest.raises(NotFoundError):
        await svc.update_group_name(GROUP_ID, OWNER_ID, "New Name")


# ── set_member_role dispatch (PATCH .../members/{user_id}) ─────────────────


async def test_set_member_role_owner_transfers_ownership() -> None:
    group = make_group()
    memberships = owner_and_member()
    svc, _db = make_service(group, memberships)
    await svc.set_member_role(GROUP_ID, OWNER_ID, MEMBER_ID, "owner")
    assert group.owner_id == MEMBER_ID
    assert memberships[(GROUP_ID, MEMBER_ID)].role == "owner"


async def test_set_member_role_member_on_owner_target_is_conflict() -> None:
    svc, _db = make_service(make_group(), owner_and_member())
    with pytest.raises(ConflictError):
        await svc.set_member_role(GROUP_ID, OWNER_ID, OWNER_ID, "member")


async def test_set_member_role_member_on_member_is_noop() -> None:
    memberships = owner_and_member()
    svc, db = make_service(make_group(), memberships)
    await svc.set_member_role(GROUP_ID, OWNER_ID, MEMBER_ID, "member")
    assert memberships[(GROUP_ID, MEMBER_ID)].role == "member"
    assert db.commits == 0


# ── QA regression: soft-deleted group must 404 on membership-gated paths ───
# (require_membership previously checked only the memberships table, so a
# soft-deleted group's member list / topics / chatrooms / invites / WS join
# path kept working. require_membership now resolves the group through
# get_group_or_404 first.)


async def test_require_membership_on_deleted_group_is_not_found() -> None:
    svc, _db = make_service(make_group(deleted=True), owner_and_member())
    with pytest.raises(NotFoundError):
        await svc.require_membership(GROUP_ID, MEMBER_ID)


async def test_require_membership_on_missing_group_is_not_found() -> None:
    svc, _db = make_service(None, owner_and_member())
    with pytest.raises(NotFoundError):
        await svc.require_membership(GROUP_ID, MEMBER_ID)


async def test_require_owner_on_deleted_group_is_not_found() -> None:
    """require_owner cascades through require_membership, so it 404s too
    (not 403) once the group itself is gone."""
    svc, _db = make_service(make_group(deleted=True), owner_and_member())
    with pytest.raises(NotFoundError):
        await svc.require_owner(GROUP_ID, OWNER_ID)


async def test_require_membership_still_forbidden_for_non_member_on_live_group() -> None:
    """Regression guard: the new existence check must not change the
    forbidden-vs-not-found split for a live group."""
    svc, _db = make_service(make_group(), owner_and_member())
    with pytest.raises(ForbiddenError):
        await svc.require_membership(GROUP_ID, OTHER_ID)


# ── QA regression: remove/leave must evict the affected user's WebSockets ──


async def test_leave_group_evicts_member_from_all_group_chatrooms(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    memberships = owner_and_member()
    svc, _db = make_service(make_group(), memberships, chatroom_ids=["chat-main", "chat-topic-1"])
    calls: list[tuple[list[str], str]] = []

    async def fake_evict(chatroom_ids: list[str], user_id: str) -> None:
        calls.append((chatroom_ids, user_id))

    monkeypatch.setattr("app.services.group_service.ws_hub.evict_user", fake_evict)

    await svc.leave_group(GROUP_ID, MEMBER_ID)

    assert calls == [(["chat-main", "chat-topic-1"], MEMBER_ID)]


async def test_soft_delete_evicts_all_sockets_from_group_chatrooms(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    svc, _db = make_service(
        make_group(), owner_and_member(), chatroom_ids=["chat-main", "chat-topic-1"]
    )
    calls: list[list[str]] = []

    async def fake_evict_room(chatroom_ids: list[str]) -> None:
        calls.append(chatroom_ids)

    monkeypatch.setattr("app.services.group_service.ws_hub.evict_room", fake_evict_room)

    await svc.soft_delete_group(GROUP_ID, OWNER_ID)

    assert calls == [["chat-main", "chat-topic-1"]]


async def test_remove_member_evicts_target_from_all_group_chatrooms(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    memberships = owner_and_member()
    svc, _db = make_service(make_group(), memberships, chatroom_ids=["chat-main"])
    calls: list[tuple[list[str], str]] = []

    async def fake_evict(chatroom_ids: list[str], user_id: str) -> None:
        calls.append((chatroom_ids, user_id))

    monkeypatch.setattr("app.services.group_service.ws_hub.evict_user", fake_evict)

    await svc.remove_member(GROUP_ID, OWNER_ID, MEMBER_ID)

    assert calls == [(["chat-main"], MEMBER_ID)]


async def test_eviction_failure_does_not_break_leave_group(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """WS cleanup errors must be swallowed — the membership change already
    committed and must not be surfaced to the HTTP caller as a failure."""
    memberships = owner_and_member()
    svc, db = make_service(make_group(), memberships, chatroom_ids=["chat-main"])

    async def boom(chatroom_ids: list[str], user_id: str) -> None:
        raise RuntimeError("ws hub unreachable")

    monkeypatch.setattr("app.services.group_service.ws_hub.evict_user", boom)

    await svc.leave_group(GROUP_ID, MEMBER_ID)  # must not raise

    assert (GROUP_ID, MEMBER_ID) not in memberships
    assert db.commits == 1
