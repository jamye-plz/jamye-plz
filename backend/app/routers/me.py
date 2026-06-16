"""Me router — current user profile endpoints."""

from fastapi import APIRouter

from app.core.deps import CurrentUser, DbSession
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserOut, UserPatch

router = APIRouter(prefix="/me", tags=["me"])


@router.get("", response_model=UserOut)
async def get_me(current_user: CurrentUser):
    return current_user


@router.patch("", response_model=UserOut)
async def patch_me(body: UserPatch, current_user: CurrentUser, db: DbSession):
    repo = UserRepository(db)
    user = await repo.update(
        current_user,
        nickname=body.nickname,
        avatar_url=body.avatar_url,
    )
    await db.commit()
    return user
