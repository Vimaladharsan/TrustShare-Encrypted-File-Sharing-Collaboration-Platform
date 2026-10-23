from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class FileInfo(BaseModel):
    """What the API returns about a file. The storage location is never exposed."""

    id: str
    name: str
    extension: str
    mime_type: str
    category: str
    size_bytes: int
    sha256: str
    folder_id: str | None
    status: Literal["active", "trashed"]
    created_at: datetime
    updated_at: datetime
    is_favorite: bool = False  # starred by the logged-in user

    @classmethod
    def from_doc(cls, doc: dict[str, Any], is_favorite: bool = False) -> "FileInfo":
        return cls(
            id=str(doc["_id"]),
            name=doc["original_name"],
            extension=doc["extension"],
            mime_type=doc["mime_type"],
            category=doc["category"],
            size_bytes=doc["size_bytes"],
            sha256=doc["sha256"],
            folder_id=str(doc["folder_id"]) if doc.get("folder_id") else None,
            status=doc["status"],
            created_at=doc["created_at"],
            updated_at=doc["updated_at"],
            is_favorite=is_favorite,
        )


class FileListResponse(BaseModel):
    items: list[FileInfo]
    total: int


class StorageUsageResponse(BaseModel):
    used_bytes: int
    quota_bytes: int


class FileUpdate(BaseModel):
    """Send `name` to rename (the extension must stay the same), `folder_id` to move
    (null = move to the top level), or both."""

    name: str | None = Field(None, min_length=1, max_length=255)
    folder_id: str | None = None
