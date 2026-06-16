"""AuthService — OAuth login/token issuance.

Real OAuth calls are made only when provider keys are provisioned.
Falls back to deterministic local stubs when keys are absent.
# TODO(oma-deferred): integrate kakao when key is provisioned
# TODO(oma-deferred): integrate google when key is provisioned
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import create_access_token
from app.models.user import User
from app.repositories.user_repository import UserRepository


class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._user_repo = UserRepository(db)

    def get_kakao_auth_url(self) -> str:
        settings = get_settings()
        if settings.kakao_enabled:
            return (
                "https://kauth.kakao.com/oauth/authorize"
                f"?client_id={settings.kakao_client_id}"
                f"&redirect_uri={settings.kakao_redirect_uri}"
                "&response_type=code"
            )
        # TODO(oma-deferred): integrate kakao when key is provisioned
        return "/api/auth/kakao/stub"

    def get_google_auth_url(self) -> str:
        settings = get_settings()
        if settings.google_enabled:
            return (
                "https://accounts.google.com/o/oauth2/v2/auth"
                f"?client_id={settings.google_client_id}"
                f"&redirect_uri={settings.google_redirect_uri}"
                "&response_type=code"
                "&scope=openid%20email%20profile"
            )
        # TODO(oma-deferred): integrate google when key is provisioned
        return "/api/auth/google/stub"

    async def kakao_callback(self, code: str) -> tuple[User, str]:
        settings = get_settings()
        if settings.kakao_enabled:
            # TODO(oma-deferred): integrate kakao when key is provisioned
            # Real path: exchange code for access token, fetch user profile
            raise NotImplementedError("Kakao OAuth real path not implemented")
        # Deterministic fallback for demo/development
        provider_id = f"kakao_stub_{code[:8]}"
        user = await self._user_repo.get_by_provider("kakao", provider_id)
        if user is None:
            user = await self._user_repo.create(
                provider="kakao",
                provider_id=provider_id,
                nickname=f"KakaoUser_{code[:6]}",
            )
            await self._db.commit()
        token = create_access_token(user.id)
        return user, token

    async def google_callback(self, code: str) -> tuple[User, str]:
        settings = get_settings()
        if settings.google_enabled:
            # TODO(oma-deferred): integrate google when key is provisioned
            raise NotImplementedError("Google OAuth real path not implemented")
        # Deterministic fallback for demo/development
        provider_id = f"google_stub_{code[:8]}"
        user = await self._user_repo.get_by_provider("google", provider_id)
        if user is None:
            user = await self._user_repo.create(
                provider="google",
                provider_id=provider_id,
                nickname=f"GoogleUser_{code[:6]}",
            )
            await self._db.commit()
        token = create_access_token(user.id)
        return user, token
