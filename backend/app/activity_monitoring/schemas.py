from datetime import date, datetime
from typing import Any

from pydantic import BaseModel


class ActivityRecord(BaseModel):
    """One activity as an admin sees it – file and folder names removed."""

    id: str
    user_id: str | None
    actor_email: str | None
    action: str
    activity_type: str
    file_id: str | None
    status: str
    ip_address: str | None
    details: dict[str, Any]
    created_at: datetime


class ActivityFeed(BaseModel):
    items: list[ActivityRecord]
    total: int


class ActivityTypeCount(BaseModel):
    activity_type: str
    success: int = 0
    failure: int = 0


class ActivitySummary(BaseModel):
    from_date: date
    to_date: date
    total: int
    failures: int
    active_users: int
    by_type: list[ActivityTypeCount]
