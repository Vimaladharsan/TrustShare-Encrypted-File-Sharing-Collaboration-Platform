"""Admin view of user activity (/api/activity-monitoring) – needs `audit:read`.

Users see their own activity at /api/activity/me; admins see everyone's, without file names.
"""

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from pymongo.asynchronous.database import AsyncDatabase
from redis.asyncio import Redis

from app.activity_monitoring.models import ACTIVITY_TYPES
from app.activity_monitoring.schemas import ActivityFeed, ActivitySummary
from app.activity_monitoring.service import FEED_CHANNEL, ActivityMonitoringService
from app.api.deps import get_token_payload, require_permission
from app.core.permissions import Perm
from app.db.mongo import get_mongo
from app.db.redis import get_redis
from app.notifications.stream import event_stream
from app.services.analytics_service import Period

router = APIRouter(
    prefix="/activity-monitoring",
    tags=["activity monitoring"],
    dependencies=[Depends(require_permission(Perm.AUDIT_READ))],
)


def service(db: AsyncDatabase = Depends(get_mongo)) -> ActivityMonitoringService:
    return ActivityMonitoringService(db)


@router.get("/activities", response_model=ActivityFeed, summary="Activity feed, newest first")
async def activities(
    user_id: str | None = Query(None, max_length=36),
    activity_type: str | None = Query(None, description=f"One of: {', '.join(ACTIVITY_TYPES)}"),
    status: str | None = Query(None, pattern="^(success|failure)$"),
    file_id: str | None = Query(None, max_length=24),
    q: str | None = Query(None, max_length=100, description="Email, IP address or action"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    monitoring: ActivityMonitoringService = Depends(service),
) -> ActivityFeed:
    return await monitoring.feed(
        user_id=user_id,
        activity_type=activity_type,
        status=status,
        file_id=file_id,
        search=q,
        limit=limit,
        offset=offset,
    )


@router.get("/summary", response_model=ActivitySummary, summary="Activity counts by type")
async def summary(
    from_date: date | None = Query(None, alias="from"),
    to_date: date | None = Query(None, alias="to"),
    tz: str = Query("UTC", max_length=64),
    monitoring: ActivityMonitoringService = Depends(service),
) -> ActivitySummary:
    return await monitoring.summary(Period(from_date, to_date, tz))


@router.get("/types", response_model=list[str], summary="Activity types used for filtering")
async def types() -> list[str]:
    return ACTIVITY_TYPES


@router.get(
    "/stream",
    summary="Live activity feed (Server-Sent Events, file names removed)",
    response_class=StreamingResponse,
)
async def stream(
    request: Request,
    payload: dict[str, Any] = Depends(get_token_payload),
    redis: Redis = Depends(get_redis),
) -> StreamingResponse:
    return StreamingResponse(
        event_stream(request, redis, FEED_CHANNEL, payload, {"channel": "activity"}, "activity"),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
    )
