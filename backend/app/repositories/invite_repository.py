"""InviteRepository — CRUD for Invite model."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.invite import Invite


class InviteRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_code(self, code: str) -> Invite | None:
        result = await self._db.execute(
            select(Invite).where(Invite.code == code)
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        group_id: str,
        created_by: str,
        code: str,
        expires_at=None,
        max_uses: int | None = None,
    ) -> Invite:
        invite = Invite(
            group_id=group_id,
            created_by=created_by,
            code=code,
            expires_at=expires_at,
            max_uses=max_uses,
        )
        self._db.add(invite)
        await self._db.flush()
        await self._db.refresh(invite)
        return invite

    async def increment_used(self, invite: Invite) -> Invite:
        invite.used_count += 1
        self._db.add(invite)
        await self._db.flush()
        await self._db.refresh(invite)
        return invite
