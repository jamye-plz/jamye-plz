"""Auth router — OAuth login, callback, and logout."""

import logging
import secrets
from collections.abc import Awaitable, Callable

from fastapi import APIRouter, Request, Response
from fastapi.responses import RedirectResponse

from app.core.config import get_settings
from app.core.deps import CurrentUser, DbSession
from app.models.user import User
from app.services.auth_service import AuthService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])

_STATE_COOKIE = "oauth_state"
_STATE_MAX_AGE = 600  # 10 minutes


def _session_redirect(token: str, *, clear_state: bool = False) -> RedirectResponse:
    """Set the session cookie and bounce the browser back into the SPA."""
    s = get_settings()
    resp = RedirectResponse(url=s.frontend_origin, status_code=303)
    resp.set_cookie(
        "access_token",
        token,
        httponly=True,
        samesite="lax",
        max_age=s.jwt_expire_seconds,
    )
    if clear_state:
        resp.delete_cookie(_STATE_COOKIE)
    return resp


def _login_error_redirect() -> RedirectResponse:
    s = get_settings()
    return RedirectResponse(url=f"{s.frontend_origin}/login?error=oauth", status_code=303)


def _provider_redirect(auth_url: str, state: str) -> RedirectResponse:
    """Redirect to the provider's consent page, remembering the CSRF state."""
    resp = RedirectResponse(url=auth_url, status_code=302)
    resp.set_cookie(
        _STATE_COOKIE, state, httponly=True, samesite="lax", max_age=_STATE_MAX_AGE
    )
    return resp


async def _finish_login(
    provider: str,
    callback: Callable[[str], Awaitable[tuple[User, str]]],
    request: Request,
    code: str | None,
    state: str | None,
    error: str | None,
) -> RedirectResponse:
    if error or not code:
        logger.warning("OAuth %s returned no code (error=%s)", provider, error)
        return _login_error_redirect()
    # CSRF: the state echoed by the provider must match our cookie.
    expected = request.cookies.get(_STATE_COOKIE)
    if not expected or not state or not secrets.compare_digest(expected, state):
        logger.warning("OAuth %s state mismatch", provider)
        return _login_error_redirect()
    try:
        _user, token = await callback(code)
    except Exception:
        logger.exception("OAuth %s callback failed", provider)
        return _login_error_redirect()
    return _session_redirect(token, clear_state=True)


# ── Kakao ──────────────────────────────────────────────────────────────────────


@router.get("/kakao")
async def kakao_login(db: DbSession):
    s = get_settings()
    svc = AuthService(db)
    if not s.kakao_enabled:
        _user, token = await svc.stub_login("kakao")
        return _session_redirect(token)
    state = secrets.token_urlsafe(24)
    return _provider_redirect(svc.get_kakao_auth_url(state), state)


@router.get("/kakao/callback")
async def kakao_callback(
    request: Request,
    db: DbSession,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
):
    svc = AuthService(db)
    return await _finish_login("kakao", svc.kakao_callback, request, code, state, error)


# ── Google ─────────────────────────────────────────────────────────────────────


@router.get("/google")
async def google_login(db: DbSession):
    s = get_settings()
    svc = AuthService(db)
    if not s.google_enabled:
        _user, token = await svc.stub_login("google")
        return _session_redirect(token)
    state = secrets.token_urlsafe(24)
    return _provider_redirect(svc.get_google_auth_url(state), state)


@router.get("/google/callback")
async def google_callback(
    request: Request,
    db: DbSession,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
):
    svc = AuthService(db)
    return await _finish_login("google", svc.google_callback, request, code, state, error)


# ── Logout ─────────────────────────────────────────────────────────────────────


@router.post("/logout")
async def logout(response: Response, current_user: CurrentUser):
    response.delete_cookie("access_token")
    return {"ok": True}
