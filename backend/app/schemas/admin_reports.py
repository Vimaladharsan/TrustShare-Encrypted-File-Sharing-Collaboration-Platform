from datetime import date, datetime
from typing import Any

from pydantic import BaseModel

from app.schemas.analytics import ActivityEntry, Metric

# ---------- Security Dashboard ----------


class SecurityMetrics(BaseModel):
    total_logins: Metric
    successful_logins: Metric
    failed_logins: Metric
    unauthorized_attempts: Metric  # unauthorized access + blocked requests
    security_events: Metric


class LoginDay(BaseModel):
    date: date
    success: int = 0
    failed: int = 0


class AccessDay(BaseModel):
    date: date
    unauthorized: int = 0
    blocked: int = 0


class TypeCount(BaseModel):
    type: str
    label: str
    count: int


class LoginEntry(BaseModel):
    user_name: str | None  # None = no account with that email
    email: str | None
    ip_address: str | None
    location: str
    status: str  # success | failed
    method: str | None  # password, Google …
    reason: str | None  # why it failed
    created_at: datetime


class SecurityEvent(BaseModel):
    type: str
    severity: str
    message: str
    actor_email: str | None
    ip_address: str | None
    details: dict[str, Any]
    created_at: datetime


class SecurityOverview(BaseModel):
    from_date: date
    to_date: date
    metrics: SecurityMetrics
    logins_by_day: list[LoginDay]
    access_by_day: list[AccessDay]
    events_by_type: list[TypeCount]
    recent_logins: list[LoginEntry]
    recent_events: list[SecurityEvent]


class LoginPage(BaseModel):
    items: list[LoginEntry]
    total: int


class SecurityEventPage(BaseModel):
    items: list[SecurityEvent]
    total: int


class AuditEntry(ActivityEntry):
    actor_email: str | None
    user_id: str | None


class AuditPage(BaseModel):
    items: list[AuditEntry]
    total: int


# ---------- Admin Dashboard / system overview ----------


class UserStats(BaseModel):
    total: int
    active: int
    disabled: int
    inactive_30_days: int
    by_role: dict[str, int]


class UserStorage(BaseModel):
    """How much one account stores – counts and sizes only, never file names or contents."""

    user_id: str
    email: str | None
    full_name: str | None
    files: int
    bytes: int
    quota_bytes: int | None


class ShareStats(BaseModel):
    links_active: int
    links_ended: int  # expired, revoked or used up
    direct_active: int
    direct_ended: int
    link_downloads: int


class ActivityDay(BaseModel):
    date: date
    uploads: int = 0
    downloads: int = 0


class KeyStats(BaseModel):
    active_version: int
    configured_versions: list[int]
    keys_by_version: dict[int, int]


class SystemOverview(BaseModel):
    users: UserStats
    total_files: int
    total_bytes: int
    storage_by_user: list[UserStorage]
    shares: ShareStats
    activity_by_day: list[ActivityDay]
    keys: KeyStats
    storage_provider: str  # e.g. "Azure Blob Storage" – admin-only, not on the public /health
    events_last_7_days: dict[str, int]  # by severity
