from datetime import datetime
from typing import Any

from pydantic import BaseModel


class Notification(BaseModel):
    id: str
    type: str
    title: str
    message: str
    severity: str
    link: str | None
    data: dict[str, Any]
    read: bool
    read_at: datetime | None
    created_at: datetime


class NotificationPage(BaseModel):
    items: list[Notification]
    total: int
    unread: int


class UnreadCount(BaseModel):
    unread: int


class MarkedRead(BaseModel):
    updated: int


class PreferenceItem(BaseModel):
    type: str
    label: str
    email: bool
    email_optional: bool


class Preferences(BaseModel):
    items: list[PreferenceItem]


class PreferencesUpdate(BaseModel):
    email: dict[str, bool]  # {type: send an email too}


class TypeStat(BaseModel):
    type: str
    sent: int
    read: int
    emails_sent: int
    emails_failed: int


class Delivery(BaseModel):
    """A notification as an admin sees it: who got what kind, and whether it arrived – no text."""

    id: str
    type: str
    severity: str
    recipient_email: str | None
    read: bool
    email_status: str
    created_at: datetime


class NotificationStats(BaseModel):
    total: int
    unread: int
    emails_sent: int
    emails_failed: int
    by_type: list[TypeStat]
    recent: list[Delivery]
