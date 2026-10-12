from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class FolderInfo(BaseModel):
    id: str
    name: str
    parent_id: str | None
    status: Literal["active", "trashed"]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_doc(cls, doc: dict[str, Any]) -> "FolderInfo":
        return cls(
            id=str(doc["_id"]),
            name=doc["name"],
            parent_id=str(doc["parent_id"]) if doc.get("parent_id") else None,
            status=doc["status"],
            created_at=doc["created_at"],
            updated_at=doc["updated_at"],
        )


class Breadcrumb(BaseModel):
    id: str
    name: str


class FolderDetail(FolderInfo):
    breadcrumbs: list[Breadcrumb]  # from the top-level folder down to this one


class FolderListResponse(BaseModel):
    items: list[FolderInfo]


class FolderCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100, examples=["Finance"])
    parent_id: str | None = Field(None, description="Empty = create at the top level")


class FolderUpdate(BaseModel):
    """Send `name` to rename, `parent_id` to move (null = move to the top level), or both."""

    name: str | None = Field(None, min_length=1, max_length=100)
    parent_id: str | None = None
