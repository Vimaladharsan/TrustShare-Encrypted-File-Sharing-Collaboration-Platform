"""MongoDB access for folders (collection "folders"). Reads and writes only – no rules.

Each folder stores `ancestors`: the IDs of all its parent folders, from the top down.
That makes breadcrumbs one query, and "everything inside this folder" one query too.
"""

from typing import Any

from bson import ObjectId
from pymongo.asynchronous.database import AsyncDatabase

from app.repositories.file_repository import to_object_id


class FolderRepository:
    def __init__(self, db: AsyncDatabase) -> None:
        self.folders = db["folders"]

    async def insert(self, doc: dict[str, Any]) -> dict[str, Any]:
        result = await self.folders.insert_one(doc)
        doc["_id"] = result.inserted_id
        return doc

    async def get(self, folder_id: str | ObjectId) -> dict[str, Any] | None:
        oid = folder_id if isinstance(folder_id, ObjectId) else to_object_id(folder_id)
        return await self.folders.find_one({"_id": oid}) if oid else None

    async def get_active_owned(self, owner_id: str, folder_id: str) -> dict[str, Any] | None:
        oid = to_object_id(folder_id)
        if oid is None:
            return None
        return await self.folders.find_one({"_id": oid, "owner_id": owner_id, "status": "active"})

    async def name_taken(
        self, owner_id: str, parent_id: ObjectId | None, name_lower: str, exclude: ObjectId | None
    ) -> bool:
        query: dict[str, Any] = {
            "owner_id": owner_id,
            "parent_id": parent_id,
            "name_lower": name_lower,
            "status": "active",
        }
        if exclude is not None:
            query["_id"] = {"$ne": exclude}
        return await self.folders.find_one(query) is not None

    async def list_children(
        self, owner_id: str, parent_id: ObjectId | None
    ) -> list[dict[str, Any]]:
        cursor = self.folders.find(
            {"owner_id": owner_id, "parent_id": parent_id, "status": "active"}
        ).sort("name_lower", 1)
        return await cursor.to_list(length=None)

    async def list_trashed(self, owner_id: str) -> list[dict[str, Any]]:
        # Only folders the user trashed directly, not the sub-folders trashed along with them.
        cursor = self.folders.find(
            {"owner_id": owner_id, "status": "trashed", "trashed_directly": True}
        ).sort("trashed_at", -1)
        return await cursor.to_list(length=None)

    async def descendants(self, folder_id: ObjectId) -> list[dict[str, Any]]:
        return await self.folders.find({"ancestors": folder_id}).to_list(length=None)

    async def get_many(self, ids: list[ObjectId]) -> list[dict[str, Any]]:
        return await self.folders.find({"_id": {"$in": ids}}).to_list(length=None)

    async def update(self, folder_id: ObjectId, changes: dict[str, Any]) -> None:
        await self.folders.update_one({"_id": folder_id}, {"$set": changes})

    async def update_many(self, ids: list[ObjectId], changes: dict[str, Any]) -> None:
        await self.folders.update_many({"_id": {"$in": ids}}, {"$set": changes})

    async def delete_many(self, ids: list[ObjectId]) -> None:
        await self.folders.delete_many({"_id": {"$in": ids}})

    async def delete_all_owned(self, owner_id: str) -> None:
        await self.folders.delete_many({"owner_id": owner_id})
