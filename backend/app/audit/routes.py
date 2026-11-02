"""Audit log retrieval (/api/audit-logs) – administrators only (`audit:read`).

The brief's endpoints: all logs, one user's logs, one file's logs, filtered logs; plus a chain
verification and a CSV export. There are no endpoints to change or delete entries.
"""

from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response
from pymongo.asynchronous.database import AsyncDatabase

from app.activity_monitoring.service import record_activity
from app.api.deps import require_permission
from app.audit.schemas import AuditLogPage, AuditVerification
from app.audit.service import AuditService, build_filter
from app.core.permissions import Perm
from app.db.mongo import get_mongo
from app.models import User
from app.services.security_events import record_security_event

can_read_audit = require_permission(Perm.AUDIT_READ)
router = APIRouter(prefix="/audit-logs", tags=["audit logs"])


def audit(db: AsyncDatabase = Depends(get_mongo)) -> AuditService:
    return AuditService(db)


@router.get(
    "",
    response_model=AuditLogPage,
    summary="All audit logs, newest first",
    dependencies=[Depends(can_read_audit)],
)
async def all_logs(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    service: AuditService = Depends(audit),
) -> AuditLogPage:
    return await service.page({}, limit, offset)


@router.get(
    "/user/{user_id}",
    response_model=AuditLogPage,
    summary="One user's audit logs",
    dependencies=[Depends(can_read_audit)],
)
async def user_logs(
    user_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    service: AuditService = Depends(audit),
) -> AuditLogPage:
    return await service.page({"user_id": user_id}, limit, offset)


@router.get(
    "/file/{file_id}",
    response_model=AuditLogPage,
    summary="Everything that happened to one file (by file ID – names are never shown to admins)",
    dependencies=[Depends(can_read_audit)],
)
async def file_logs(
    file_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    service: AuditService = Depends(audit),
) -> AuditLogPage:
    return await service.page({"file_id": file_id}, limit, offset)


@router.get(
    "/filter",
    response_model=AuditLogPage,
    summary="Filter by user, activity type, file ID, status and date range",
    dependencies=[Depends(can_read_audit)],
)
async def filtered_logs(
    user_id: str | None = Query(None, max_length=36),
    activity_type: str | None = Query(None, max_length=30),
    file_id: str | None = Query(None, max_length=24),
    status: str | None = Query(None, pattern="^(success|failure)$"),
    q: str | None = Query(None, max_length=100, description="Username, IP, action or text"),
    from_date: date | None = Query(None, alias="from"),
    to_date: date | None = Query(None, alias="to"),
    tz: str = Query("UTC", max_length=64),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    service: AuditService = Depends(audit),
) -> AuditLogPage:
    match = build_filter(
        user_id=user_id,
        activity_type=activity_type,
        file_id=file_id,
        status=status,
        search=q,
        from_date=from_date,
        to_date=to_date,
        tz=tz,
    )
    return await service.page(match, limit, offset)


@router.get(
    "/verify",
    response_model=AuditVerification,
    summary="Re-compute every hash: has any audit entry been changed or deleted?",
    dependencies=[Depends(can_read_audit)],
)
async def verify(service: AuditService = Depends(audit)) -> AuditVerification:
    return await service.verify()


@router.get("/export", summary="Download filtered audit logs as CSV (max 10,000 rows)")
async def export(
    request: Request,
    user_id: str | None = Query(None, max_length=36),
    activity_type: str | None = Query(None, max_length=30),
    file_id: str | None = Query(None, max_length=24),
    status: str | None = Query(None, pattern="^(success|failure)$"),
    q: str | None = Query(None, max_length=100),
    from_date: date | None = Query(None, alias="from"),
    to_date: date | None = Query(None, alias="to"),
    tz: str = Query("UTC", max_length=64),
    admin: User = Depends(can_read_audit),
    service: AuditService = Depends(audit),
    db: AsyncDatabase = Depends(get_mongo),
) -> Response:
    match = build_filter(
        user_id=user_id,
        activity_type=activity_type,
        file_id=file_id,
        status=status,
        search=q,
        from_date=from_date,
        to_date=to_date,
        tz=tz,
    )
    text, rows = await service.csv(match)
    filters = {"activity_type": activity_type, "status": status, "rows": rows}
    # Exporting the audit trail is itself audited and raised as an admin security event.
    await record_activity(
        request, admin, "admin.audit_export", resource_type="audit_log", details=filters, db=db
    )
    await record_security_event(
        "admin_action",
        request=request,
        user=admin,
        message=f"Exported the audit log ({rows} rows)",
        details=filters,
    )
    return Response(
        content="﻿" + text,  # byte-order mark: Excel shows accented names correctly
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": (
                f'attachment; filename="trustshare-audit-logs-{datetime.now(UTC):%Y%m%d-%H%M}.csv"'
            )
        },
    )
