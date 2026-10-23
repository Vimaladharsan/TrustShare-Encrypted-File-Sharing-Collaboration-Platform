"""Admin reports. Every route checks a permission on the server (RBAC): a normal user who calls
these URLs directly gets 403 – hiding the admin menu is only a convenience."""

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pymongo.asynchronous.database import AsyncDatabase
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_permission
from app.core.permissions import Perm
from app.db.mongo import get_mongo
from app.db.postgres import get_db
from app.schemas.admin_reports import (
    AuditPage,
    LoginPage,
    SecurityEventPage,
    SecurityOverview,
    SystemOverview,
)
from app.services.admin_reports_service import AdminReportsService
from app.services.analytics_service import Period

router = APIRouter(prefix="/admin", tags=["admin reports"])

can_read_audit = require_permission(Perm.AUDIT_READ)
can_read_users = require_permission(Perm.USER_READ)


def reports(
    session: AsyncSession = Depends(get_db), db: AsyncDatabase = Depends(get_mongo)
) -> AdminReportsService:
    return AdminReportsService(session, db)


def period(
    from_date: date | None = Query(None, alias="from", description="First day (YYYY-MM-DD)"),
    to_date: date | None = Query(None, alias="to", description="Last day, included"),
    tz: str = Query("UTC", max_length=64, description='Time zone for days, e.g. "Asia/Kolkata"'),
) -> Period:
    return Period(from_date, to_date, tz)


@router.get(
    "/security/overview",
    response_model=SecurityOverview,
    summary="Security Dashboard: metrics, charts, recent logins and events (audit:read)",
    dependencies=[Depends(can_read_audit)],
)
async def security_overview(
    selected: Period = Depends(period), service: AdminReportsService = Depends(reports)
) -> SecurityOverview:
    return await service.security_overview(selected)


@router.get(
    "/security/logins",
    response_model=LoginPage,
    summary="Login history of all users (audit:read)",
    dependencies=[Depends(can_read_audit)],
)
async def logins(
    status: Literal["success", "failed"] | None = None,
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    service: AdminReportsService = Depends(reports),
) -> LoginPage:
    return await service.logins(status, limit, offset)


@router.get(
    "/security/events",
    response_model=SecurityEventPage,
    summary="Security events, newest first (audit:read)",
    dependencies=[Depends(can_read_audit)],
)
async def security_events(
    severity: Literal["high", "medium", "low", "info"] | None = None,
    type: str | None = Query(None, max_length=40, description="e.g. account_locked"),
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    service: AdminReportsService = Depends(reports),
) -> SecurityEventPage:
    return await service.security_events(severity, type, limit, offset)


@router.get(
    "/audit",
    response_model=AuditPage,
    summary="Audit log of every user's activity, with search and filters (audit:read)",
    dependencies=[Depends(can_read_audit)],
)
async def audit_log(
    q: str | None = Query(None, max_length=100, description="Email, action or IP address"),
    group: Literal["auth", "files", "sharing", "admin"] | None = None,
    status: Literal["success", "failure"] | None = None,
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    service: AdminReportsService = Depends(reports),
) -> AuditPage:
    return await service.audit(q, group, status, limit, offset)


@router.get(
    "/overview",
    response_model=SystemOverview,
    summary="Admin Dashboard: users, storage per account, sharing, activity, keys (user:read)",
    dependencies=[Depends(can_read_users)],
)
async def system_overview(
    selected: Period = Depends(period), service: AdminReportsService = Depends(reports)
) -> SystemOverview:
    return await service.system_overview(selected)
