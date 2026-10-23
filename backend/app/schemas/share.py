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
    """

    share_type: ShareType
    permission: SharePermission = "view"
    expires_at: datetime | None = None
    max_downloads: int | None = Field(None, ge=1, le=1000)
    recipient_email: EmailStr | None = None

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
        return self


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
    status: ShareStatus
    created_at: datetime
    last_accessed_at: datetime | None


class ShareCreated(ShareInfo):
    # The full link – returned ONLY in this response. The server keeps just its SHA-256 hash.
    url: str | None = None


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
