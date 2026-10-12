"""MongoDB access for file metadata (collection "files"). Reads and writes only – no rules."""

import re
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
from pymongo.asynchronous.database import AsyncDatabase

SORT_FIELDS = {"name": "name_lower", "size": "size_bytes", "date": "created_at"}


def to_object_id(value: str) -> ObjectId | None:
    try:
        return ObjectId(value)
    except (InvalidId, TypeError):
        return None


class FileRepository:
    def __init__(self, db: AsyncDatabase) -> None:
        self.files = db["files"]

    async def insert(self, doc: dict[str, Any]) -> dict[str, Any]:
        result = await self.files.insert_one(doc)
        doc["_id"] = result.inserted_id
        return doc

    async def get(self, file_id: str) -> dict[str, Any] | None:
        oid = to_object_id(file_id)
        return await self.files.find_one({"_id": oid}) if oid else None

    async def find_duplicate(
        self, owner_id: str, sha256: str, folder_id: ObjectId | None
    ) -> dict[str, Any] | None:
        return await self.files.find_one(
            {"owner_id": owner_id, "sha256": sha256, "folder_id": folder_id, "status": "active"}
        )

    async def used_bytes(self, owner_id: str) -> int:
        """Total size of everything the user stores (trashed files still count)."""
        cursor = await self.files.aggregate(
            [
                {"$match": {"owner_id": owner_id}},
                {"$group": {"_id": None, "used": {"$sum": "$size_bytes"}}},
            ]
        )
        result = await cursor.to_list(length=1)
        return result[0]["used"] if result else 0

    async def list_owned(
        self,
        owner_id: str,
        *,
        search: str | None,
        category: str | None,
        sort: str,
        order: str,
        limit: int,
        offset: int,
    ) -> tuple[list[dict[str, Any]], int]:
        query: dict[str, Any] = {"owner_id": owner_id, "status": "active"}
        if search:
            # re.escape: user input is matched literally, never as a regular expression.
            query["name_lower"] = {"$regex": re.escape(search.lower())}
        if category:
            query["category"] = category
        direction = 1 if order == "asc" else -1
        total = await self.files.count_documents(query)
        cursor = self.files.find(query).sort(SORT_FIELDS[sort], direction).skip(offset).limit(limit)
        return await cursor.to_list(length=limit), total
