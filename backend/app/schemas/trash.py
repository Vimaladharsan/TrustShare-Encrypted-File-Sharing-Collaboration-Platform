from typing import Literal

from pydantic import BaseModel, Field


class TrashSelection(BaseModel):
    """The items ticked in the trash."""

    file_ids: list[str] = Field(default_factory=list, max_length=500)
    folder_ids: list[str] = Field(default_factory=list, max_length=500)


class FailedItem(BaseModel):
    id: str
    type: Literal["file", "folder"]
    code: str
    message: str


class BulkResult(BaseModel):
    succeeded: int
    failed: list[FailedItem]
