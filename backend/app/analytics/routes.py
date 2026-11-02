"""Storage analytics (/api/analytics/…) – administrators only (`audit:read`).

The brief's endpoints: storage, users/storage, files, downloads, sharing. Filters: date range,
user, file type, activity type. (A user's own File Analytics stays at /api/analytics/me.)
"""

from datetime import date

from fastapi import APIRouter, Depends, Query
from pymongo.asynchronous.database import AsyncDatabase
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.queries import Filters
from app.analytics.schemas import (
    DownloadStatistics,
    FileStatistics,
    SharingStatistics,
    StorageAnalytics,
    UserStorageList,
)
from app.analytics.service import AnalyticsService
from app.api.deps import require_permission
from app.core.permissions import Perm
from app.db.mongo import get_mongo
from app.db.postgres import get_db
from app.services.analytics_service import Period

router = APIRouter(
    prefix="/analytics",
    tags=["storage analytics"],
    dependencies=[Depends(require_permission(Perm.AUDIT_READ))],
)


def filters(
    from_date: date | None = Query(None, alias="from", description="First day (YYYY-MM-DD)"),
    to_date: date | None = Query(None, alias="to", description="Last day, included"),
    tz: str = Query("UTC", max_length=64),
    user_id: str | None = Query(None, max_length=36),
    file_type: str | None = Query(
        None, pattern="^(document|spreadsheet|presentation|image|text|other)$"
    ),
    activity_type: str | None = Query(None, max_length=30),
    file_id: str | None = Query(None, max_length=24),
) -> Filters:
    return Filters(
        period=Period(from_date, to_date, tz),
        user_id=user_id,
        file_type=file_type,
        activity_type=activity_type,
        file_id=file_id,
    )


def service(
    session: AsyncSession = Depends(get_db), db: AsyncDatabase = Depends(get_mongo)
) -> AnalyticsService:
    return AnalyticsService(session, db)


@router.get("/storage", response_model=StorageAnalytics, summary="Total storage usage")
async def storage(
    f: Filters = Depends(filters), analytics: AnalyticsService = Depends(service)
) -> StorageAnalytics:
    return await analytics.storage(f)


@router.get("/users/storage", response_model=UserStorageList, summary="Storage used by each user")
async def users_storage(
    f: Filters = Depends(filters), analytics: AnalyticsService = Depends(service)
) -> UserStorageList:
    return await analytics.users_storage(f)


@router.get("/files", response_model=FileStatistics, summary="File statistics (uploads by date)")
async def files(
    f: Filters = Depends(filters), analytics: AnalyticsService = Depends(service)
) -> FileStatistics:
    return await analytics.files_statistics(f)


@router.get("/downloads", response_model=DownloadStatistics, summary="Download statistics")
async def downloads(
    f: Filters = Depends(filters), analytics: AnalyticsService = Depends(service)
) -> DownloadStatistics:
    return await analytics.downloads_statistics(f)


@router.get("/sharing", response_model=SharingStatistics, summary="Sharing statistics")
async def sharing(
    f: Filters = Depends(filters), analytics: AnalyticsService = Depends(service)
) -> SharingStatistics:
    return await analytics.sharing_statistics(f)
