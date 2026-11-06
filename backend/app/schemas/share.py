import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, model_validator

ShareType = Literal["link", "user"]
SharePermission = Literal["view", "download"]
ShareStatus = Literal["active", "expired", "revoked", "used_up", "file_unavailable"]


class ShareCreate(BaseModel):
    """Create a share link (`share_type: "link"`) or share with a registered person
    (`share_type: "user"` + `recipient_email`).

    - `permission`: "view" = preview in the browser only, "download" = preview + download
    - `expires_at`: required for links (at most SHARE_LINK_MAX_DAYS ahead), optional for people
    - `max_downloads`: optional download limit (needs "download" permission)
    - `password`: optional password for a link – visitors must enter it first (links only)
    """

    share_type: ShareType
    permission: SharePermission = "view"
    expires_at: datetime | None = None
    max_downloads: int | None = Field(None, ge=1, le=1000)
    recipient_email: EmailStr | None = None
    password: str | None = Field(None, min_length=4, max_length=72)

    @model_validator(mode="after")
    def check_combination(self) -> "ShareCreate":
        if self.share_type == "user" and not self.recipient_email:
            raise ValueError("recipient_email is required when sharing with a person")
        if self.share_type == "link" and self.recipient_email:
            raise ValueError("recipient_email is only used when sharing with a person")
        if self.max_downloads and self.permission != "download":
            raise ValueError("A download limit needs the download permission")
        if self.expires_at and self.expires_at.tzinfo is None:
            raise ValueError("expires_at must include a time zone, e.g. 2026-11-01T12:00:00Z")
        if self.password and self.share_type != "link":
            raise ValueError("A password can only be set for share links")
        return self


class ShareBulkCreate(ShareCreate):
    """Share several of my files at once with the same settings: one link per file
    (`share_type: "link"`), or one person gets access to all of them (`share_type: "user"`)."""

    file_ids: list[str] = Field(min_length=1, max_length=50)


class BulkShareFailure(BaseModel):
    file_id: str
    code: str
    message: str


class ShareUpdate(BaseModel):
    """Change an existing share without revoking it – send only what changes.

    - `permission`: "view" or "download" (switching to view also removes a download limit)
    - `expires_at`: new expiry; links need one (within SHARE_LINK_MAX_DAYS), people may have null
      (= never expires)
    - `max_downloads`: new download limit, null = no limit; not below the downloads already made

    Extending an expired share or raising a used-up limit makes it active again (same link).
    A revoked share is final.
    """

    permission: SharePermission | None = None
    expires_at: datetime | None = None
    max_downloads: int | None = Field(None, ge=1, le=1000)
    password: str | None = Field(None, min_length=4, max_length=72)  # links: new one, null = remove

    @model_validator(mode="after")
    def check_values(self) -> "ShareUpdate":
        if not self.model_fields_set:
            raise ValueError("Nothing to change")
        if "permission" in self.model_fields_set and self.permission is None:
            raise ValueError("permission must be view or download")
        if self.expires_at and self.expires_at.tzinfo is None:
            raise ValueError("expires_at must include a time zone, e.g. 2026-11-01T12:00:00Z")
        return self


class ShareAccessEvent(BaseModel):
    """One use of a share, as its owner sees it."""

    at: datetime
    event: Literal["opened", "viewed", "downloaded", "refused"]
    detail: str | None  # why it was refused, e.g. "link expired"
    visitor: str  # the person's name for direct shares, "Anonymous visitor" for links
    visitor_email: str | None
    device: str  # e.g. "Chrome on Windows"
    kind: Literal["mobile", "desktop"]
    ip: str | None  # last part hidden for the visitor's privacy, e.g. "203.0.113.x"


class ShareAccessSummary(BaseModel):
    opened: int
    viewed: int
    downloaded: int
    refused: int
    visitors: int  # distinct people / devices


class ShareAccessHistory(BaseModel):
    share_id: uuid.UUID
    summary: ShareAccessSummary
    items: list[ShareAccessEvent]  # newest first, at most 200


class ShareInfo(BaseModel):
    """A share as its owner sees it. Never contains the link token or its hash."""

    id: uuid.UUID
    file_id: str
    file_name: str | None  # None if the file no longer exists
    share_type: ShareType
    permission: SharePermission
    recipient_email: str | None
    recipient_name: str | None
    expires_at: datetime | None
    max_downloads: int | None
    download_count: int
    has_password: bool = False
    status: ShareStatus
    created_at: datetime
    last_accessed_at: datetime | None


class ShareCreated(ShareInfo):
    # The full link – returned ONLY in this response. The server keeps just its SHA-256 hash.
    url: str | None = None


class BulkShareResult(BaseModel):
    created: list[ShareCreated]  # links include their url – shown only in this response
    failed: list[BulkShareFailure]


class ShareListResponse(BaseModel):
    items: list[ShareInfo]


class ReceivedShare(BaseModel):
    """A file someone shared with me ("Shared with Me")."""

    id: uuid.UUID  # share id – used for preview/download
    file_id: str
    file_name: str
    extension: str
    mime_type: str
    category: str
    size_bytes: int
    permission: SharePermission
    owner_name: str
    owner_email: str
    expires_at: datetime | None
    shared_at: datetime
    can_preview: bool


class ReceivedShareListResponse(BaseModel):
    items: list[ReceivedShare]


class PublicShareInfo(BaseModel):
    """What a link visitor sees before opening the file (no account needed)."""

    file_name: str
    extension: str
    mime_type: str
    category: str
    size_bytes: int
    permission: SharePermission
    owner_name: str
    expires_at: datetime | None
    downloads_left: int | None  # None = no limit
    can_preview: bool
