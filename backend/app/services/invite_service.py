"""InviteService — invite code generation and redemption."""

import secrets
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    ForbiddenError,
    InviteExhaustedError,
    InviteExpiredError,
    NotFoundError,
)
from app.models.invite import Invite
from app.repositories.invite_repository import InviteRepository


class InviteService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._invite_repo = InviteRepository(db)

    async def create_invite(
        self,
        group_id: str,
        created_by: str,
        expires_at: datetime | None = None,
        max_uses: int | None = None,
    ) -> Invite:
        code = secrets.token_urlsafe(12)
        invite = await self._invite_repo.create(
            group_id=group_id,
            created_by=created_by,
            code=code,
            expires_at=expires_at,
            max_uses=max_uses,
        )
        await self._db.commit()
        await self._db.refresh(invite)
        return invite

    async def validate_and_consume(self, code: str, user_id: str) -> Invite:
        invite = await self._invite_repo.get_by_code(code)
        if invite is None:
            raise NotFoundError("Invite", code)
        now = datetime.now(timezone.utc)
        if invite.expires_at and invite.expires_at < now:
            raise InviteExpiredError()
        if invite.max_uses is not None and invite.used_count >= invite.max_uses:
            raise InviteExhaustedError()
        invite = await self._invite_repo.increment_used(invite)
        await self._db.commit()
        return invite

    async def get_invite_or_404(self, code: str) -> Invite:
        invite = await self._invite_repo.get_by_code(code)
        if invite is None:
            raise NotFoundError("Invite", code)
        return invite
