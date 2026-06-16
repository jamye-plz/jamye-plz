"""GroupRepository — CRUD for Group and Membership models."""

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
            select(Group).where(Group.id == group_id)
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
            .where(Membership.user_id == user_id)
        )
        return list(result.scalars().all())

    async def member_count(self, group_id: str) -> int:
        result = await self._db.execute(
            select(Membership).where(Membership.group_id == group_id)
        )
        return len(result.scalars().all())


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
        result = await self._db.execute(
            select(Membership).where(Membership.group_id == group_id)
        )
        return list(result.scalars().all())


class ChatroomRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_id(self, chatroom_id: str) -> Chatroom | None:
        result = await self._db.execute(
            select(Chatroom).where(Chatroom.id == chatroom_id)
        )
        return result.scalar_one_or_none()

    async def get_main_by_group(self, group_id: str) -> Chatroom | None:
        result = await self._db.execute(
            select(Chatroom).where(
                Chatroom.group_id == group_id,
                Chatroom.type == "main",
            )
        )
        return result.scalar_one_or_none()

    async def create(self, group_id: str, type: str, topic_id: str | None = None) -> Chatroom:
        chatroom = Chatroom(group_id=group_id, type=type, topic_id=topic_id)
        self._db.add(chatroom)
        await self._db.flush()
        await self._db.refresh(chatroom)
        return chatroom
