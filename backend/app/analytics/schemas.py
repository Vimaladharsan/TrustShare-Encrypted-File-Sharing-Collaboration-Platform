from datetime import date, datetime

from pydantic import BaseModel


class CategoryStorage(BaseModel):
    category: str
    files: int
    bytes: int


class LocationStorage(BaseModel):
    location: str  # azure | s3 | local (Milestone 1 files)
    files: int
    bytes: int


class StorageAnalytics(BaseModel):
    total_bytes: int
    total_files: int
    active_bytes: int
    trash_bytes: int
    vault_bytes: int
    vault_files: int
    users_with_files: int
    quota_total_bytes: int
    by_category: list[CategoryStorage]
    by_location: list[LocationStorage]


class UserStorage(BaseModel):
    user_id: str
    email: str | None
    full_name: str | None
    role: str | None
    files: int
    bytes: int
    vault_files: int
    vault_bytes: int
    quota_bytes: int | None
    percent_used: float
    last_upload_at: datetime | None


class UserStorageList(BaseModel):
    total_bytes: int
    items: list[UserStorage]


class UploadDay(BaseModel):
    date: date
    document: int = 0
    spreadsheet: int = 0
    presentation: int = 0
    image: int = 0
    text: int = 0
    other: int = 0


class TopFile(BaseModel):
    file_id: str
    extension: str | None
    category: str
    owner_email: str | None
    downloads: int


class FileStatistics(BaseModel):
    from_date: date
    to_date: date
    uploaded: int  # in the period
    rejected_uploads: int
    downloaded: int
    shared_files: int  # distinct files shared in the period
    total_files: int  # stored now
    total_bytes: int
    uploads_by_day: list[UploadDay]
    most_downloaded: list[TopFile]


class DownloadDay(BaseModel):
    date: date
    owner: int = 0
    direct_share: int = 0
    link: int = 0


class UserCount(BaseModel):
    user_id: str | None
    email: str | None  # None = anonymous link visitors
    count: int


class DownloadStatistics(BaseModel):
    from_date: date
    to_date: date
    total: int
    unique_users: int
    by_owner: int
    via_direct_share: int
    via_link: int
    failed_attempts: int
    by_day: list[DownloadDay]
    most_downloaded: list[TopFile]
    by_user: list[UserCount]


class ShareDay(BaseModel):
    date: date
    link: int = 0
    direct: int = 0


class SharingStatistics(BaseModel):
    from_date: date
    to_date: date
    created: int
    link_shares: int
    direct_shares: int
    shared_files: int
    active: int  # status right now, for shares created in the period
    expired: int
    revoked: int
    used_up: int
    by_day: list[ShareDay]
    by_owner: list[UserCount]
    top_recipients: list[UserCount]
