"""Notifications router — in-app notification listing and read marking."""

from datetime import datetime

from fastapi import APIRouter, Query, status
from pydantic import BaseModel

from app.core.deps import CurrentUser, DbSession
from app.services.notification_service import NotificationService


class NotificationItem(BaseModel):
    id: str
    user_id: str
    kind: str
    title: str
    body: str
    action_url: str | None = None
    read: bool
    created_at: datetime


class NotificationListResponse(BaseModel):
    items: list[NotificationItem]
    unread_count: int


router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=NotificationListResponse)
async def list_notifications(
    current_user: CurrentUser,
    db: DbSession,
    limit: int = Query(50, ge=1, le=200),
):
    svc = NotificationService(db)
    items, unread_count = await svc.list_view(current_user.id, limit=limit)
    return NotificationListResponse(
        items=[NotificationItem(**item) for item in items],
        unread_count=unread_count,
    )


@router.post("/{notification_id}/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_notification_read(notification_id: str, current_user: CurrentUser, db: DbSession):
    svc = NotificationService(db)
    await svc.mark_read(notification_id, current_user.id)
