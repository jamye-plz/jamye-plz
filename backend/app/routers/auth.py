"""Auth router — OAuth login and logout endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, DbSession
from app.core.config import get_settings
from app.db.session import get_db
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/kakao")
async def kakao_login():
    settings = get_settings()
    svc = AuthService(db=None)  # type: ignore[arg-type]
    url = svc.get_kakao_auth_url()
    if settings.kakao_enabled:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=url)
    return {"auth_url": url, "note": "kakao not configured — use stub"}


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
async def google_login():
    settings = get_settings()
    svc = AuthService(db=None)  # type: ignore[arg-type]
    url = svc.get_google_auth_url()
    if settings.google_enabled:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=url)
    return {"auth_url": url, "note": "google not configured — use stub"}


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
