"""AuthService — OAuth login and JWT issuance.

When provider keys are set, the real OAuth flow runs (authorization-code →
token exchange → profile fetch → user upsert). Without keys, a deterministic
local stub is used so development works offline.
"""

import logging
from urllib.parse import urlencode

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import create_access_token
from app.models.user import User
from app.repositories.user_repository import UserRepository

logger = logging.getLogger(__name__)

# ── Provider endpoints ─────────────────────────────────────────────────────────
KAKAO_AUTH_URL = "https://kauth.kakao.com/oauth/authorize"
KAKAO_TOKEN_URL = "https://kauth.kakao.com/oauth/token"
KAKAO_PROFILE_URL = "https://kapi.kakao.com/v2/user/me"
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._user_repo = UserRepository(db)

    # ── Authorization URLs ─────────────────────────────────────────────────────

    def get_kakao_auth_url(self, state: str) -> str:
        s = get_settings()
        params = {
            "client_id": s.kakao_client_id,
            "redirect_uri": s.kakao_redirect_uri,
            "response_type": "code",
            "scope": "profile_nickname,profile_image",
            "state": state,
        }
        return f"{KAKAO_AUTH_URL}?{urlencode(params)}"

    def get_google_auth_url(self, state: str) -> str:
        s = get_settings()
        params = {
            "client_id": s.google_client_id,
            "redirect_uri": s.google_redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
        }
        return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"

    # ── User upsert + token ────────────────────────────────────────────────────

    async def _issue_session(
        self, provider: str, provider_id: str, nickname: str, avatar_url: str | None
    ) -> tuple[User, str]:
        """Find-or-create the user and mint a JWT. On re-login we keep the
        user's existing nickname/avatar (they may have edited their profile)."""
        user = await self._user_repo.get_by_provider(provider, provider_id)
        if user is None:
            # Normalize provider values to the DB column limits (nickname 64,
            # avatar_url 512) so long names/URLs don't fail the INSERT.
            nickname = (nickname or provider.capitalize())[:64]
            avatar_url = avatar_url[:512] if avatar_url else None
            user = await self._user_repo.create(
                provider=provider,
                provider_id=provider_id,
                nickname=nickname,
                avatar_url=avatar_url,
            )
            await self._db.commit()
        return user, create_access_token(user.id)

    async def stub_login(self, provider: str) -> tuple[User, str]:
        """Issue a session for a deterministic stub user when keys are absent."""
        provider_id = f"{provider}_stub_dev"
        return await self._issue_session(provider, provider_id, f"{provider.capitalize()}Dev", None)

    # ── Real OAuth callbacks ───────────────────────────────────────────────────

    async def kakao_callback(self, code: str) -> tuple[User, str]:
        s = get_settings()
        async with httpx.AsyncClient(timeout=10.0) as client:
            token_data = {
                "grant_type": "authorization_code",
                "client_id": s.kakao_client_id,
                "redirect_uri": s.kakao_redirect_uri,
                "code": code,
            }
            if s.kakao_client_secret:
                token_data["client_secret"] = s.kakao_client_secret
            tr = await client.post(KAKAO_TOKEN_URL, data=token_data)
            tr.raise_for_status()
            access_token = tr.json()["access_token"]

            pr = await client.get(
                KAKAO_PROFILE_URL, headers={"Authorization": f"Bearer {access_token}"}
            )
            pr.raise_for_status()
            profile = pr.json()

        provider_id = str(profile["id"])
        account = profile.get("kakao_account", {}).get("profile", {})
        nickname = account.get("nickname") or f"카카오{provider_id[:6]}"
        avatar_url = account.get("profile_image_url")
        return await self._issue_session("kakao", provider_id, nickname, avatar_url)

    async def google_callback(self, code: str) -> tuple[User, str]:
        s = get_settings()
        async with httpx.AsyncClient(timeout=10.0) as client:
            tr = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "client_id": s.google_client_id,
                    "client_secret": s.google_client_secret,
                    "redirect_uri": s.google_redirect_uri,
                    "code": code,
                },
            )
            tr.raise_for_status()
            access_token = tr.json()["access_token"]

            ir = await client.get(
                GOOGLE_USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"}
            )
            ir.raise_for_status()
            info = ir.json()

        provider_id = info["sub"]
        nickname = (
            info.get("name") or (info.get("email") or "").split("@")[0] or f"구글{provider_id[:6]}"
        )
        avatar_url = info.get("picture")
        return await self._issue_session("google", provider_id, nickname, avatar_url)
