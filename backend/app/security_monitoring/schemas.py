from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class SecurityAlert(BaseModel):
    """A security event as an alert: what happened, how serious, and where it is in the workflow."""

    id: str
    alert_id: str | None
    type: str
    title: str
    severity: str  # high | medium | low | info
    status: str  # open | acknowledged | resolved
    message: str
    user_id: str | None
    actor_email: str | None
    ip_address: str | None
    rule: dict[str, Any] | None  # rule-based detections: name, count, limit, window, subject
    details: dict[str, Any]  # file and folder names removed
    created_at: datetime
    acknowledged_by: str | None = None
    acknowledged_at: datetime | None = None
    resolved_by: str | None = None
    resolved_at: datetime | None = None
    note: str | None = None


class SecurityAlertPage(BaseModel):
    items: list[SecurityAlert]
    total: int


class AlertUpdate(BaseModel):
    action: Literal["acknowledge", "resolve", "reopen"]
    note: str | None = Field(None, max_length=500)


class TypeCount(BaseModel):
    type: str
    title: str
    count: int


class MonitoringSummary(BaseModel):
    from_date: date
    to_date: date
    total_events: int
    open_alerts: int
    by_severity: dict[str, int]
    failed_logins: int
    unauthorized_attempts: int
    suspicious_downloads: int
    expired_link_attempts: int
    revoked_link_attempts: int
    alerts_by_type: list[TypeCount]
    recent_alerts: list[SecurityAlert]


class DetectionRule(BaseModel):
    name: str
    title: str
    severity: str
    counts: str
    per: str
    limit: int
    window_minutes: int
    condition: str
