"""Unit tests for creator-only topic title update (BE-1).

Tests are pure service / schema level — no DB engine, no HTTP test client.
Fakes implement only the methods TopicService.update_topic and
GroupService.require_membership actually call, so a signature drift in the
real repository surfaces as an AttributeError here.
"""

import pytest
from pydantic import ValidationError

from app.core.exceptions import ForbiddenError
from app.models.group import Group
from app.models.membership import Membership
from app.models.topic import Topic
from app.schemas.topic import TopicPatch
from app.services.group_service import GroupService
from app.services.topic_service import TopicService

GROUP_ID = "group-1"
TOPIC_ID = "topic-1"
AUTHOR_ID = "user-author"
MEMBER_ID = "user-member"
OTHER_ID = "user-other"


# ── Fakes ────────────────────────────────────────────────────────────────────


class FakeDb:
    """Stands in for AsyncSession: no-op transaction control."""

    def __init__(self) -> None:
        self.commits = 0

    def add(self, obj: object) -> None:
        pass

    async def commit(self) -> None:
        self.commits += 1

    async def flush(self) -> None:
        pass

    async def refresh(self, obj: object) -> None:
        pass


class FakeTopicRepo:
    def __init__(self, topic: Topic | None) -> None:
        self._topic = topic

    async def get_by_id(self, topic_id: str) -> Topic | None:
        if self._topic and self._topic.id == topic_id:
            return self._topic
        return None

    async def update(
        self,
        topic: Topic,
        title: str | None = None,
        body: str | None = None,
        status: str | None = None,
    ) -> Topic:
        if title is not None:
            topic.title = title
        if body is not None:
            topic.body = body
        if status is not None:
            topic.status = status
        return topic


class FakeGroupRepo:
    def __init__(self, group: Group) -> None:
        self._group = group

    async def get_by_id(self, group_id: str) -> Group | None:
        if self._group.id == group_id:
            return self._group
        return None


class FakeMembershipRepo:
    def __init__(self, memberships: dict[tuple[str, str], Membership]) -> None:
        self._memberships = memberships

    async def get(self, group_id: str, user_id: str) -> Membership | None:
        return self._memberships.get((group_id, user_id))


# ── Helpers ───────────────────────────────────────────────────────────────────


def make_topic(author_id: str = AUTHOR_ID, status: str = "seed") -> Topic:
    return Topic(
        id=TOPIC_ID,
        group_id=GROUP_ID,
        author_id=author_id,
        title="원래 제목",
        body=None,
        status=status,
    )


def make_topic_svc(topic: Topic | None) -> tuple[TopicService, FakeDb]:
    db = FakeDb()
    svc = TopicService(db)
    svc._topic_repo = FakeTopicRepo(topic)  # type: ignore[attr-defined]
    return svc, db


def make_group_svc(
    memberships: dict[tuple[str, str], Membership],
    deleted: bool = False,
) -> GroupService:
    from datetime import datetime, timezone

    group = Group(
        id=GROUP_ID,
        name="테스트 그룹",
        owner_id=AUTHOR_ID,
        max_members=12,
        deleted_at=datetime.now(timezone.utc) if deleted else None,
    )
    db = FakeDb()
    svc = GroupService(db)
    svc._group_repo = FakeGroupRepo(group)  # type: ignore[attr-defined]
    svc._membership_repo = FakeMembershipRepo(memberships)  # type: ignore[attr-defined]
    return svc


def author_membership() -> dict[tuple[str, str], Membership]:
    return {
        (GROUP_ID, AUTHOR_ID): Membership(
            id="m-author", group_id=GROUP_ID, user_id=AUTHOR_ID, role="member"
        )
    }


# ── Schema validation ─────────────────────────────────────────────────────────


def test_empty_title_is_rejected() -> None:
    with pytest.raises(ValidationError):
        TopicPatch(title="")


def test_whitespace_only_title_is_rejected() -> None:
    with pytest.raises(ValidationError):
        TopicPatch(title="   ")


def test_title_exceeding_256_chars_is_rejected() -> None:
    with pytest.raises(ValidationError):
        TopicPatch(title="가" * 257)


def test_title_exactly_256_chars_is_allowed() -> None:
    patch = TopicPatch(title="a" * 256)
    assert patch.title == "a" * 256


def test_title_is_stripped_server_side() -> None:
    patch = TopicPatch(title="  새 제목  ")
    assert patch.title == "새 제목"


def test_null_title_is_allowed() -> None:
    assert TopicPatch(title=None).title is None


# ── Author title update ───────────────────────────────────────────────────────


async def test_author_can_update_title() -> None:
    topic = make_topic()
    svc, db = make_topic_svc(topic)
    result = await svc.update_topic(TOPIC_ID, AUTHOR_ID, title="새 제목")
    assert result.title == "새 제목"
    assert db.commits == 1


async def test_title_only_patch_does_not_set_enriched_status() -> None:
    topic = make_topic(status="seed")
    svc, _ = make_topic_svc(topic)
    result = await svc.update_topic(TOPIC_ID, AUTHOR_ID, title="새 제목")
    assert result.status == "seed"


# ── Body update behavior is compatible ────────────────────────────────────────


async def test_body_update_still_works() -> None:
    topic = make_topic()
    svc, db = make_topic_svc(topic)
    result = await svc.update_topic(TOPIC_ID, AUTHOR_ID, body="새 본문", status="enriched")
    assert result.body == "새 본문"
    assert result.status == "enriched"
    assert db.commits == 1


async def test_title_and_body_together_sets_enriched_via_status_param() -> None:
    topic = make_topic()
    svc, _ = make_topic_svc(topic)
    result = await svc.update_topic(
        TOPIC_ID, AUTHOR_ID, title="제목", body="본문", status="enriched"
    )
    assert result.title == "제목"
    assert result.status == "enriched"


# ── Non-author member receives 403 ────────────────────────────────────────────


async def test_non_author_member_is_forbidden() -> None:
    """A group member who is not the topic author must be denied (service layer)."""
    topic = make_topic(author_id=AUTHOR_ID)
    svc, _ = make_topic_svc(topic)
    with pytest.raises(ForbiddenError, match="Only the topic author"):
        await svc.update_topic(TOPIC_ID, MEMBER_ID, title="탈취 시도")


# ── Non-member receives 403 via require_membership ────────────────────────────


async def test_non_member_is_forbidden_by_require_membership() -> None:
    """A caller with no group membership must be denied before reaching the service."""
    svc = make_group_svc(memberships=author_membership())
    with pytest.raises(ForbiddenError):
        await svc.require_membership(GROUP_ID, OTHER_ID)
