"""FastAPI dependency injection helpers."""

from typing import Annotated

from fastapi import Cookie, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthenticationError
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import User
from app.repositories.user_repository import UserRepository


async def get_current_user(
    access_token: Annotated[str | None, Cookie(alias="access_token")] = None,
    db: AsyncSession = Depends(get_db),
) -> User:
    """Extract and validate JWT from httpOnly cookie, return the User model.

    Raises:
        AuthenticationError: if cookie absent or token invalid.
    """
    if not access_token:
        raise AuthenticationError("Not authenticated")
    payload = decode_access_token(access_token)
    user_id: str | None = payload.get("sub")
    if not user_id:
        raise AuthenticationError("Token missing subject claim")

    repo = UserRepository(db)
    user = await repo.get_by_id(user_id)
    if user is None:
        raise AuthenticationError("User not found")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
DbSession = Annotated[AsyncSession, Depends(get_db)]
