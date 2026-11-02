"""Notifications (/api/notifications): the signed-in user's own notifications, preferences and
the live stream; plus delivery statistics for administrators (Notification Management)."""

from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from pymongo.asynchronous.database import AsyncDatabase
from redis.asyncio import Redis

from app.api.deps import get_current_user, get_token_payload, require_permission
from app.core.permissions import Perm
from app.db.mongo import get_mongo
from app.db.redis import get_redis
from app.models import User
from app.notifications.models import TYPES, channel
from app.notifications.schemas import (
    MarkedRead,
    Notification,
    NotificationPage,
    NotificationStats,
    Preferences,
    PreferencesUpdate,
    UnreadCount,
)
from app.notifications.service import NotificationService
from app.notifications.stream import event_stream

router = APIRouter(prefix="/notifications", tags=["notifications"])


def service(
    db: AsyncDatabase = Depends(get_mongo), redis: Redis = Depends(get_redis)
) -> NotificationService:
    return NotificationService(db, redis)


@router.get("", response_model=NotificationPage, summary="My notifications, newest first")
async def list_notifications(
    unread: bool = Query(False, description="Only unread ones"),
    type: str | None = Query(None, description=f"One of: {', '.join(TYPES)}"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    notifications: NotificationService = Depends(service),
) -> NotificationPage:
    return await notifications.page(user, unread, type, limit, offset)


@router.get("/unread-count", response_model=UnreadCount, summary="Number of unread notifications")
async def unread_count(
    user: User = Depends(get_current_user),
    notifications: NotificationService = Depends(service),
) -> UnreadCount:
    return UnreadCount(unread=await notifications.unread(user))


@router.post("/read-all", response_model=MarkedRead, summary="Mark all my notifications as read")
async def read_all(
    user: User = Depends(get_current_user),
    notifications: NotificationService = Depends(service),
) -> MarkedRead:
    return MarkedRead(updated=await notifications.mark_all_read(user))


@router.post("/{notification_id}/read", response_model=Notification, summary="Mark one as read")
async def read_one(
    notification_id: str,
    user: User = Depends(get_current_user),
    notifications: NotificationService = Depends(service),
) -> Notification:
    return await notifications.mark_read(user, notification_id)


@router.get(
    "/preferences", response_model=Preferences, summary="Which notifications I get by email"
)
async def get_preferences(
    user: User = Depends(get_current_user),
    notifications: NotificationService = Depends(service),
) -> Preferences:
    return await notifications.preferences(user)


@router.put("/preferences", response_model=Preferences, summary="Turn email per type on or off")
async def put_preferences(
    data: PreferencesUpdate,
    user: User = Depends(get_current_user),
    notifications: NotificationService = Depends(service),
) -> Preferences:
    return await notifications.update_preferences(user, data.email)


@router.get(
    "/stream",
    summary="Live notifications (Server-Sent Events) – read with fetch + Authorization header",
    response_class=StreamingResponse,
)
async def stream(
    request: Request,
    user: User = Depends(get_current_user),
    payload: dict[str, Any] = Depends(get_token_payload),
    redis: Redis = Depends(get_redis),
    notifications: NotificationService = Depends(service),
) -> StreamingResponse:
    ready = {"unread": await notifications.unread(user)}
    return StreamingResponse(
        event_stream(request, redis, channel(str(user.id)), payload, ready),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
    )


@router.get(
    "/admin/stats",
    response_model=NotificationStats,
    summary="Notification Management: totals, email delivery, recent deliveries (no message text)",
    dependencies=[Depends(require_permission(Perm.AUDIT_READ))],
)
async def admin_stats(notifications: NotificationService = Depends(service)) -> NotificationStats:
    return await notifications.stats()
