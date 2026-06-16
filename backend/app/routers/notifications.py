"""Notifications router — in-app notification listing and read marking."""

from fastapi import APIRouter, Query

from app.core.deps import CurrentUser, DbSession
from app.services.notification_service import NotificationService
from pydantic import BaseModel
from datetime import datetime


class NotificationOut(BaseModel):
    id: str
    user_id: str
    type: str
    payload: dict
    read_at: datetime | None = None
    created_at: datetime

    class Config:
        from_attributes = True


router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationOut])
async def list_notifications(
    current_user: CurrentUser,
    db: DbSession,
    limit: int = Query(50, ge=1, le=200),
):
    svc = NotificationService(db)
    return await svc.list_notifications(current_user.id, limit=limit)


@router.post("/{notification_id}/read", response_model=NotificationOut)
async def mark_notification_read(
    notification_id: str, current_user: CurrentUser, db: DbSession
):
    svc = NotificationService(db)
    return await svc.mark_read(notification_id, current_user.id)
