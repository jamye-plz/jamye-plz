"""GroupService — group and membership business logic."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    AlreadyMemberError,
    ForbiddenError,
    GroupFullError,
    NotFoundError,
)
from app.models.group import Group
from app.models.membership import Membership
from app.repositories.group_repository import (
    ChatroomRepository,
    GroupRepository,
    MembershipRepository,
)


class GroupService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._group_repo = GroupRepository(db)
        self._membership_repo = MembershipRepository(db)
        self._chatroom_repo = ChatroomRepository(db)

    async def create_group(self, name: str, owner_id: str) -> Group:
        group = await self._group_repo.create(name=name, owner_id=owner_id)
        # Add owner as a member with role "owner"
        await self._membership_repo.create(group_id=group.id, user_id=owner_id, role="owner")
        # Create the default main chatroom
        await self._chatroom_repo.create(group_id=group.id, type="main")
        await self._db.commit()
        await self._db.refresh(group)
        return group

    async def list_user_groups(self, user_id: str) -> list[Group]:
        return await self._group_repo.list_by_user(user_id)

    async def get_main_chatroom_id(self, group_id: str) -> str | None:
        chatroom = await self._chatroom_repo.get_main_by_group(group_id)
        return chatroom.id if chatroom else None

    async def get_member_count(self, group_id: str) -> int:
        return await self._group_repo.member_count(group_id)

    async def get_group_or_404(self, group_id: str) -> Group:
        group = await self._group_repo.get_by_id(group_id)
        if group is None:
            raise NotFoundError("Group", group_id)
        return group

    async def require_membership(self, group_id: str, user_id: str) -> Membership:
        membership = await self._membership_repo.get(group_id, user_id)
        if membership is None:
            raise ForbiddenError("You are not a member of this group")
        return membership

    async def require_owner(self, group_id: str, user_id: str) -> Membership:
        membership = await self.require_membership(group_id, user_id)
        if membership.role != "owner":
            raise ForbiddenError("Only the group owner can perform this action")
        return membership

    async def list_members(self, group_id: str) -> list[Membership]:
        return await self._membership_repo.list_by_group(group_id)

    async def join_via_invite(self, group_id: str, user_id: str) -> Membership:
        """Add a user to a group. Caller must validate the invite beforehand."""
        existing = await self._membership_repo.get(group_id, user_id)
        if existing:
            raise AlreadyMemberError()
        group = await self.get_group_or_404(group_id)
        count = await self._group_repo.member_count(group_id)
        if count >= group.max_members:
            raise GroupFullError()
        membership = await self._membership_repo.create(
            group_id=group_id, user_id=user_id, role="member"
        )
        await self._db.commit()
        return membership
