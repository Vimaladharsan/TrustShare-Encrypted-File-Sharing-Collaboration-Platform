"""Security monitoring (/api/security-monitoring) – administrators only (`audit:read`)."""

from datetime import date

from fastapi import APIRouter, Depends, Query, Request
from pymongo.asynchronous.database import AsyncDatabase

from app.api.deps import require_permission
from app.core.permissions import Perm
from app.db.mongo import get_mongo
from app.models import User
from app.security_monitoring.detection import describe_rules
from app.security_monitoring.schemas import (
    AlertUpdate,
    DetectionRule,
    MonitoringSummary,
    SecurityAlert,
    SecurityAlertPage,
)
from app.security_monitoring.service import SecurityMonitoringService
from app.services.analytics_service import Period

can_read_audit = require_permission(Perm.AUDIT_READ)
router = APIRouter(prefix="/security-monitoring", tags=["security monitoring"])


def service(db: AsyncDatabase = Depends(get_mongo)) -> SecurityMonitoringService:
    return SecurityMonitoringService(db)


@router.get(
    "/summary",
    response_model=MonitoringSummary,
    summary="Totals for the Security Monitoring section (default: last 30 days)",
    dependencies=[Depends(can_read_audit)],
)
async def summary(
    from_date: date | None = Query(None, alias="from"),
    to_date: date | None = Query(None, alias="to"),
    tz: str = Query("UTC", max_length=64),
    monitoring: SecurityMonitoringService = Depends(service),
) -> MonitoringSummary:
    return await monitoring.summary(Period(from_date, to_date, tz))


@router.get(
    "/events",
    response_model=SecurityAlertPage,
    summary="Security events / alerts – filter by user, type, severity, status and dates",
    dependencies=[Depends(can_read_audit)],
)
async def events(
    user: str | None = Query(None, max_length=100, description="User ID or part of an email"),
    type: str | None = Query(None, max_length=40),
    severity: str | None = Query(None, pattern="^(high|medium|low|info)$"),
    status: str | None = Query(None, pattern="^(open|acknowledged|resolved)$"),
    from_date: date | None = Query(None, alias="from"),
    to_date: date | None = Query(None, alias="to"),
    tz: str = Query("UTC", max_length=64),
    limit: int = Query(25, ge=1, le=200),
    offset: int = Query(0, ge=0),
    monitoring: SecurityMonitoringService = Depends(service),
) -> SecurityAlertPage:
    return await monitoring.alerts(
        user=user,
        event_type=type,
        severity=severity,
        status=status,
        from_date=from_date,
        to_date=to_date,
        tz=tz,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/events/{alert_id}",
    response_model=SecurityAlert,
    summary="One alert",
    dependencies=[Depends(can_read_audit)],
)
async def get_event(
    alert_id: str, monitoring: SecurityMonitoringService = Depends(service)
) -> SecurityAlert:
    return await monitoring.get(alert_id)


@router.patch(
    "/events/{alert_id}",
    response_model=SecurityAlert,
    summary="Acknowledge, resolve (with a note) or reopen an alert",
)
async def update_event(
    alert_id: str,
    change: AlertUpdate,
    request: Request,
    admin: User = Depends(can_read_audit),
    monitoring: SecurityMonitoringService = Depends(service),
) -> SecurityAlert:
    return await monitoring.update(alert_id, change, admin, request)


@router.get(
    "/rules",
    response_model=list[DetectionRule],
    summary="Detection rules and their current thresholds",
    dependencies=[Depends(can_read_audit)],
)
async def rules() -> list[DetectionRule]:
    return [DetectionRule(**rule) for rule in describe_rules()]
