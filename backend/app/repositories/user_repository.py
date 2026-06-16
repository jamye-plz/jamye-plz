"""UserRepository — CRUD for User model."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UserRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_id(self, user_id: str) -> User | None:
        result = await self._db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_provider(self, provider: str, provider_id: str) -> User | None:
        result = await self._db.execute(
            select(User).where(
                User.provider == provider,
                User.provider_id == provider_id,
            )
        )
        return result.scalar_one_or_none()

    async def create(
        self, provider: str, provider_id: str, nickname: str, avatar_url: str | None = None
    ) -> User:
        user = User(
            provider=provider,
            provider_id=provider_id,
            nickname=nickname,
            avatar_url=avatar_url,
        )
        self._db.add(user)
        await self._db.flush()
        await self._db.refresh(user)
        return user

    async def update(
        self, user: User, nickname: str | None = None, avatar_url: str | None = None
    ) -> User:
        if nickname is not None:
            user.nickname = nickname
        if avatar_url is not None:
            user.avatar_url = avatar_url
        self._db.add(user)
        await self._db.flush()
        await self._db.refresh(user)
        return user
