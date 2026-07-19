"""GroupService — group and membership business logic."""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import ws_hub
from app.core.exceptions import (
    AlreadyMemberError,
    ConflictError,
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
from app.repositories.user_repository import UserRepository
from app.schemas.group import GroupMemberOut

logger = logging.getLogger(__name__)


class GroupService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._group_repo = GroupRepository(db)
        self._membership_repo = MembershipRepository(db)
        self._chatroom_repo = ChatroomRepository(db)
        self._user_repo = UserRepository(db)

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
        """Verify the group is alive (not soft-deleted) and the user belongs to
        it. Checking existence first, before membership, closes the gap where a
        soft-deleted group's memberships row is untouched: without this, every
        membership-gated path (member list, topics, chatrooms, invites,
        require_owner) would keep working against a "deleted" group."""
        await self.get_group_or_404(group_id)
        membership = await self._membership_repo.get(group_id, user_id)
        if membership is None:
            raise ForbiddenError("You are not a member of this group")
        return membership

    async def is_member(self, group_id: str, user_id: str) -> bool:
        return await self._membership_repo.get(group_id, user_id) is not None

    async def require_owner(self, group_id: str, user_id: str) -> Membership:
        membership = await self.require_membership(group_id, user_id)
        if membership.role != "owner":
            raise ForbiddenError("Only the group owner can perform this action")
        return membership

    async def list_members(self, group_id: str) -> list[Membership]:
        return await self._membership_repo.list_by_group(group_id)

    async def list_members_out(self, group_id: str) -> list[GroupMemberOut]:
        """Members enriched with each user's nickname + avatar, owner first."""
        memberships = await self._membership_repo.list_by_group(group_id)
        out: list[GroupMemberOut] = []
        for m in memberships:
            user = await self._user_repo.get_by_id(m.user_id)
            out.append(
                GroupMemberOut(
                    user_id=m.user_id,
                    nickname=user.nickname if user else "(알 수 없음)",
                    avatar_url=user.avatar_url if user else None,
                    role=m.role,
                    joined_at=m.joined_at,
                )
            )
        # Owner first, then members in join order.
        out.sort(key=lambda x: (x.role != "owner", x.joined_at))
        return out

    async def update_group_name(self, group_id: str, actor_id: str, name: str) -> Group:
        # require_owner -> require_membership already 404s a missing/soft-deleted
        # group before the ownership check, so no separate existence check here.
        await self.require_owner(group_id, actor_id)
        group = await self._group_repo.update_name(group_id, name)
        if group is None:
            raise NotFoundError("Group", group_id)
        await self._db.commit()
        await self._db.refresh(group)
        return group

    async def soft_delete_group(self, group_id: str, actor_id: str) -> None:
        await self.require_owner(group_id, actor_id)
        await self._group_repo.soft_delete(group_id)
        await self._db.commit()

    async def remove_member(self, group_id: str, actor_id: str, target_user_id: str) -> None:
        """Owner-only removal of another member. Owner removing self is not
        allowed here — ownership must be transferred first (leave semantics)."""
        await self.require_owner(group_id, actor_id)
        target_membership = await self._membership_repo.get(group_id, target_user_id)
        if target_membership is None:
            raise NotFoundError("Member", target_user_id)
        if target_user_id == actor_id:
            raise ConflictError("owner must transfer ownership before leaving")
        await self._membership_repo.delete(target_membership)
        await self._db.commit()
        await self._evict_from_group_chatrooms(group_id, target_user_id)

    async def leave_group(self, group_id: str, actor_id: str) -> None:
        membership = await self.require_membership(group_id, actor_id)
        if membership.role == "owner":
            raise ConflictError("owner must transfer ownership before leaving")
        await self._membership_repo.delete(membership)
        await self._db.commit()
        await self._evict_from_group_chatrooms(group_id, actor_id)

    async def _evict_from_group_chatrooms(self, group_id: str, user_id: str) -> None:
        """Best-effort: disconnect the user's live WebSocket(s) from every
        chatroom in this group (main + topic chatrooms) so a removed/leaving
        member stops receiving broadcasts for a group they no longer belong
        to. Never raises — WS cleanup must not fail the HTTP request that
        already committed the membership change."""
        try:
            chatrooms = await self._chatroom_repo.list_by_group(group_id)
            chatroom_ids = [c.id for c in chatrooms]
            if chatroom_ids:
                await ws_hub.evict_user(chatroom_ids, user_id)
        except Exception:
            logger.exception(
                "Failed to evict user %s from group %s chatrooms after membership change",
                user_id,
                group_id,
            )

    async def transfer_ownership(self, group_id: str, actor_id: str, target_user_id: str) -> Group:
        group = await self.get_group_or_404(group_id)
        actor_membership = await self.require_owner(group_id, actor_id)
        target_membership = await self._membership_repo.get(group_id, target_user_id)
        if target_membership is None:
            raise NotFoundError("Member", target_user_id)
        if target_membership.role == "owner":
            raise ConflictError("target user is already the owner")
        group.owner_id = target_user_id
        self._db.add(group)
        await self._membership_repo.update_role(target_membership, "owner")
        await self._membership_repo.update_role(actor_membership, "member")
        await self._db.commit()
        await self._db.refresh(group)
        return group

    async def set_member_role(
        self, group_id: str, actor_id: str, target_user_id: str, role: str
    ) -> None:
        """Owner-only role change. "owner" transfers ownership (see
        transfer_ownership); "member" on an existing non-owner member is a
        no-op; "member" on the current owner is rejected — transfer first."""
        if role == "owner":
            await self.transfer_ownership(group_id, actor_id, target_user_id)
            return
        await self.require_owner(group_id, actor_id)
        target_membership = await self._membership_repo.get(group_id, target_user_id)
        if target_membership is None:
            raise NotFoundError("Member", target_user_id)
        if target_membership.role == "owner":
            raise ConflictError("cannot demote the current owner; transfer ownership instead")
        # Already "member" — no-op.

    async def join_via_invite(self, group_id: str, user_id: str) -> Membership:
        """Add a user to a group. Caller validates the invite and commits, so
        the whole redemption stays in one transaction (does NOT commit here)."""
        existing = await self._membership_repo.get(group_id, user_id)
        if existing:
            raise AlreadyMemberError()
        group = await self.get_group_or_404(group_id)
        count = await self._group_repo.member_count(group_id)
        if count >= group.max_members:
            raise GroupFullError()
        return await self._membership_repo.create(group_id=group_id, user_id=user_id, role="member")
