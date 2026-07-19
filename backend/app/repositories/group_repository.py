"""GroupRepository — CRUD for Group and Membership models."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chatroom import Chatroom
from app.models.group import Group
from app.models.membership import Membership


class GroupRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_id(self, group_id: str) -> Group | None:
        result = await self._db.execute(
            select(Group).where(Group.id == group_id, Group.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    async def create(self, name: str, owner_id: str, max_members: int = 12) -> Group:
        group = Group(name=name, owner_id=owner_id, max_members=max_members)
        self._db.add(group)
        await self._db.flush()
        await self._db.refresh(group)
        return group

    async def list_by_user(self, user_id: str) -> list[Group]:
        result = await self._db.execute(
            select(Group)
            .join(Membership, Membership.group_id == Group.id)
            .where(Membership.user_id == user_id, Group.deleted_at.is_(None))
        )
        return list(result.scalars().all())

    async def member_count(self, group_id: str) -> int:
        # Counts memberships only (no join to `groups`), so it is unaffected by
        # the Group.deleted_at filter. Callers resolve the group through
        # get_by_id/get_group_or_404 first, which already enforces the
        # not-deleted invariant, so a deleted group's id never reaches here
        # via a live request path.
        result = await self._db.execute(select(Membership).where(Membership.group_id == group_id))
        return len(result.scalars().all())

    async def update_name(self, group_id: str, name: str) -> Group | None:
        group = await self.get_by_id(group_id)
        if group is None:
            return None
        group.name = name
        self._db.add(group)
        await self._db.flush()
        await self._db.refresh(group)
        return group

    async def soft_delete(self, group_id: str) -> None:
        group = await self.get_by_id(group_id)
        if group is None:
            return
        group.deleted_at = datetime.now(timezone.utc)
        self._db.add(group)
        await self._db.flush()


class MembershipRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get(self, group_id: str, user_id: str) -> Membership | None:
        result = await self._db.execute(
            select(Membership).where(
                Membership.group_id == group_id,
                Membership.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def create(self, group_id: str, user_id: str, role: str = "member") -> Membership:
        membership = Membership(group_id=group_id, user_id=user_id, role=role)
        self._db.add(membership)
        await self._db.flush()
        await self._db.refresh(membership)
        return membership

    async def list_by_group(self, group_id: str) -> list[Membership]:
        result = await self._db.execute(select(Membership).where(Membership.group_id == group_id))
        return list(result.scalars().all())

    async def delete(self, membership: Membership) -> None:
        await self._db.delete(membership)
        await self._db.flush()

    async def update_role(self, membership: Membership, role: str) -> Membership:
        membership.role = role
        self._db.add(membership)
        await self._db.flush()
        await self._db.refresh(membership)
        return membership


class ChatroomRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_id(self, chatroom_id: str) -> Chatroom | None:
        result = await self._db.execute(select(Chatroom).where(Chatroom.id == chatroom_id))
        return result.scalar_one_or_none()

    async def get_main_by_group(self, group_id: str) -> Chatroom | None:
        result = await self._db.execute(
            select(Chatroom).where(
                Chatroom.group_id == group_id,
                Chatroom.type == "main",
            )
        )
        return result.scalar_one_or_none()

    async def get_by_topic(self, topic_id: str) -> Chatroom | None:
        result = await self._db.execute(
            select(Chatroom).where(
                Chatroom.topic_id == topic_id,
                Chatroom.type == "topic",
            )
        )
        return result.scalar_one_or_none()

    async def list_by_group(self, group_id: str) -> list[Chatroom]:
        """All chatrooms for a group (main + one per topic)."""
        result = await self._db.execute(select(Chatroom).where(Chatroom.group_id == group_id))
        return list(result.scalars().all())

    async def create(self, group_id: str, type: str, topic_id: str | None = None) -> Chatroom:
        chatroom = Chatroom(group_id=group_id, type=type, topic_id=topic_id)
        self._db.add(chatroom)
        await self._db.flush()
        await self._db.refresh(chatroom)
        return chatroom
