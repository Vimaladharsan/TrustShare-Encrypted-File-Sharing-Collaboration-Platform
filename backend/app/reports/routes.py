"""File activity and security reports (/api/reports/…) – administrators only (`audit:read`).

Every report takes the same filters (date range, user, file type, activity type, file ID) and
`format=csv` downloads its main table.
"""

from typing import Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from pymongo.asynchronous.database import AsyncDatabase
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.queries import Filters, csv_response
from app.analytics.routes import filters
from app.api.deps import require_permission
from app.core.permissions import Perm
from app.db.mongo import get_mongo
from app.db.postgres import get_db
from app.reports.schemas import Report
from app.reports.service import ReportsService

router = APIRouter(
    prefix="/reports",
    tags=["reports"],
    dependencies=[Depends(require_permission(Perm.AUDIT_READ))],
)
Format = Literal["json", "csv"]


def service(
    session: AsyncSession = Depends(get_db), db: AsyncDatabase = Depends(get_mongo)
) -> ReportsService:
    return ReportsService(session, db)


def _out(report: Report, format: Format) -> Report | Response:
    if format == "csv":
        return csv_response(f"{report.report}-report", report.columns, report.rows)
    return report


@router.get("/uploads", response_model=Report, summary="File upload report")
async def uploads(
    format: Format = Query("json"),
    f: Filters = Depends(filters),
    reports: ReportsService = Depends(service),
) -> Report | Response:
    return _out(await reports.uploads(f), format)


@router.get("/downloads", response_model=Report, summary="File download report")
async def downloads(
    format: Format = Query("json"),
    f: Filters = Depends(filters),
    reports: ReportsService = Depends(service),
) -> Report | Response:
    return _out(await reports.downloads(f), format)


@router.get("/sharing", response_model=Report, summary="File sharing report")
async def sharing(
    format: Format = Query("json"),
    f: Filters = Depends(filters),
    reports: ReportsService = Depends(service),
) -> Report | Response:
    return _out(await reports.sharing(f), format)


@router.get("/users/{account_id}", response_model=Report, summary="One user's activity report")
async def user_activity(
    account_id: str,
    format: Format = Query("json"),
    f: Filters = Depends(filters),
    reports: ReportsService = Depends(service),
) -> Report | Response:
    return _out(await reports.user_activity(account_id, f), format)


@router.get("/security", response_model=Report, summary="Security report")
async def security(
    format: Format = Query("json"),
    f: Filters = Depends(filters),
    reports: ReportsService = Depends(service),
) -> Report | Response:
    return _out(await reports.security(f), format)
