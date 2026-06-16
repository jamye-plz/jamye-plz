"""Auth router — OAuth login and logout endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, DbSession
from app.core.config import get_settings
from app.db.session import get_db
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


def _stub_login_redirect(token: str) -> RedirectResponse:
    """Set the session cookie and bounce the browser back to the SPA."""
    settings = get_settings()
    resp = RedirectResponse(url=settings.frontend_origin, status_code=303)
    resp.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=settings.jwt_expire_seconds,
    )
    return resp


@router.get("/kakao")
async def kakao_login(db: DbSession):
    settings = get_settings()
    svc = AuthService(db)
    if settings.kakao_enabled:
        return RedirectResponse(url=svc.get_kakao_auth_url())
    # Keyless dev: mint a session for a stub user and return to the SPA.
    _user, token = await svc.stub_login("kakao")
    return _stub_login_redirect(token)


@router.get("/kakao/callback")
async def kakao_callback(code: str, response: Response, db: DbSession):
    svc = AuthService(db)
    try:
        user, token = await svc.kakao_callback(code)
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc))
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=604800,
    )
    return {"user_id": user.id, "nickname": user.nickname}


@router.get("/google")
async def google_login(db: DbSession):
    settings = get_settings()
    svc = AuthService(db)
    if settings.google_enabled:
        return RedirectResponse(url=svc.get_google_auth_url())
    # Keyless dev: mint a session for a stub user and return to the SPA.
    _user, token = await svc.stub_login("google")
    return _stub_login_redirect(token)


@router.get("/google/callback")
async def google_callback(code: str, response: Response, db: DbSession):
    svc = AuthService(db)
    try:
        user, token = await svc.google_callback(code)
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc))
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=604800,
    )
    return {"user_id": user.id, "nickname": user.nickname}


@router.post("/logout")
async def logout(response: Response, current_user: CurrentUser):
    response.delete_cookie("access_token")
    return {"ok": True}
