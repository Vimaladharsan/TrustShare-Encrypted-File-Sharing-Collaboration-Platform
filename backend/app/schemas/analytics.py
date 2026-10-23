from datetime import date, datetime
from typing import Any

from pydantic import BaseModel

from app.schemas.file import FileInfo


class CategoryUsage(BaseModel):
    category: str  # document | spreadsheet | presentation | image | text
    bytes: int
    files: int


class StorageReport(BaseModel):
    """The Storage page: quota, breakdown by type, what is in the trash, largest files."""

    used_bytes: int
    quota_bytes: int
    trash_bytes: int
    by_category: list[CategoryUsage]
    largest: list[FileInfo]


class RecentFile(BaseModel):
    file: FileInfo
    last_action: str  # e.g. "file.download"
    last_activity_at: datetime


class RecentFilesResponse(BaseModel):
    items: list[RecentFile]


# ---------- File Analytics ----------


class Metric(BaseModel):
    value: int
    previous: int  # same-length period just before the selected one ("vs last period")


class AnalyticsSummary(BaseModel):
    storage_used_bytes: int
    quota_bytes: int
    uploads: Metric
    downloads: Metric
    shares: Metric


class UploadDay(BaseModel):
    date: date
    document: int = 0
    spreadsheet: int = 0
    presentation: int = 0
    image: int = 0
    text: int = 0


class DownloadDay(BaseModel):
    date: date
    total: int = 0
    unique_users: int = 0
    shared: int = 0  # through a share link or a direct share


class ShareDay(BaseModel):
    date: date
    link: int = 0
    direct: int = 0  # with a registered TrustShare user (internal sharing)


class RecentDownload(BaseModel):
    file_id: str | None
    file_name: str
    category: str
    size_bytes: int | None  # None if the file has since been deleted
    downloaded_by: str  # "You", the user's email, or "Link visitor"
    via: str  # owner | direct_share | link
    created_at: datetime


class FileAnalytics(BaseModel):
    from_date: date
    to_date: date
    timezone: str
    summary: AnalyticsSummary
    storage_by_category: list[CategoryUsage]
    uploads_by_day: list[UploadDay]
    downloads_by_day: list[DownloadDay]
    shares_by_day: list[ShareDay]
    recent_uploads: list[FileInfo]
    recent_downloads: list[RecentDownload]


# ---------- my activity log ----------


class ActivityEntry(BaseModel):
    action: str
    status: str
    resource_type: str | None
    resource_id: str | None
    ip_address: str | None
    user_agent: str | None
    details: dict[str, Any]
    created_at: datetime


class ActivityPage(BaseModel):
    items: list[ActivityEntry]
    total: int
