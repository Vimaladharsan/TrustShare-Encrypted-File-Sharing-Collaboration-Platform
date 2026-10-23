from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pymongo.asynchronous.database import AsyncDatabase

from app.api.deps import can_read_files, get_current_user
from app.db.mongo import get_mongo
from app.models import User
from app.schemas.analytics import ActivityPage, FileAnalytics
from app.services.analytics_service import AnalyticsService, Period

router = APIRouter(tags=["analytics"])


@router.get(
    "/analytics/me",
    response_model=FileAnalytics,
    summary="File Analytics for my files (default: last 30 days)",
)
async def my_analytics(
    from_date: date | None = Query(None, alias="from", description="First day (YYYY-MM-DD)"),
    to_date: date | None = Query(None, alias="to", description="Last day, included"),
    tz: str = Query("UTC", max_length=64, description='Time zone for days, e.g. "Asia/Kolkata"'),
    user: User = Depends(can_read_files),
    db: AsyncDatabase = Depends(get_mongo),
) -> FileAnalytics:
    return await AnalyticsService(db).file_analytics(user, Period(from_date, to_date, tz))


@router.get("/activity/me", response_model=ActivityPage, summary="My own activity log")
async def my_activity(
    group: Literal["auth", "files", "sharing"] | None = Query(
        None, description="auth = logins & account, files = files & folders, sharing = shares"
    ),
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncDatabase = Depends(get_mongo),
) -> ActivityPage:
    return await AnalyticsService(db).my_activity(user, group, limit, offset)
