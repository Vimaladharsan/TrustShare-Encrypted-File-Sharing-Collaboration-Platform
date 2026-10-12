"""Folder rules: create, list, breadcrumbs, rename, move, trash, restore.

Only the owner can see or change a folder; anyone else gets 404.
"""

import re
import unicodedata
from datetime import UTC, datetime
from typing import Any

from fastapi import Request
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import DuplicateKeyError

from app.core.errors import AppError
from app.models import User
from app.repositories.folder_repository import FolderRepository
from app.schemas.folder import Breadcrumb
from app.services.activity_service import ActivityService


def _not_found() -> AppError:
    return AppError("FOLDER_NOT_FOUND", "Folder not found.", 404)


def _name_taken() -> AppError:
    return AppError("FOLDER_EXISTS", "A folder with this name already exists here.", 409)


def clean_folder_name(raw: str) -> str:
    name = unicodedata.normalize("NFC", raw)
    name = "".join(ch for ch in name if unicodedata.category(ch)[0] != "C")
    name = re.sub(r"\s+", " ", name).strip()
    if not name or name in {".", ".."} or "/" in name or "\\" in name:
        raise AppError("INVALID_NAME", "Folder names can't be empty or contain / or \\.", 400)
    return name[:100]


class FolderService:
    def __init__(self, db: AsyncDatabase, request: Request) -> None:
        self.folders = FolderRepository(db)
        self.files = db["files"]
        self.activity = ActivityService(db)
        self.request = request

    # ---------- reading ----------

    async def owned(self, user: User, folder_id: str, *, active: bool = True) -> dict[str, Any]:
        doc = await self.folders.get(folder_id)
        if doc is None or doc["owner_id"] != str(user.id):
            raise _not_found()
        if active and doc["status"] != "active":
            raise _not_found()
        return doc

    async def list_children(self, user: User, parent_id: str | None) -> list[dict[str, Any]]:
        parent = await self.owned(user, parent_id) if parent_id else None
        return await self.folders.list_children(str(user.id), parent["_id"] if parent else None)

    async def list_trashed(self, user: User) -> list[dict[str, Any]]:
        return await self.folders.list_trashed(str(user.id))

    async def breadcrumbs(self, doc: dict[str, Any]) -> list[Breadcrumb]:
        """The path from the top-level folder down to this one, in one query."""
        parents = {f["_id"]: f for f in await self.folders.get_many(doc["ancestors"])}
        chain = [parents[a] for a in doc["ancestors"] if a in parents] + [doc]
        return [Breadcrumb(id=str(f["_id"]), name=f["name"]) for f in chain]

    # ---------- changing ----------

    async def create(self, user: User, name: str, parent_id: str | None) -> dict[str, Any]:
        name = clean_folder_name(name)
        parent = await self.owned(user, parent_id) if parent_id else None
        parent_oid = parent["_id"] if parent else None
        if await self.folders.name_taken(str(user.id), parent_oid, name.lower(), None):
            raise _name_taken()
        now = datetime.now(UTC)
        try:
            doc = await self.folders.insert(
                {
                    "owner_id": str(user.id),
                    "name": name,
                    "name_lower": name.lower(),
                    "parent_id": parent_oid,
                    "ancestors": [*parent["ancestors"], parent["_id"]] if parent else [],
                    "status": "active",
                    "trashed_at": None,
                    "trashed_directly": False,
                    "created_at": now,
                    "updated_at": now,
                }
            )
        except DuplicateKeyError as exc:  # two requests at the same moment
            raise _name_taken() from exc
        await self._log(user, "folder.create", doc, {"name": name})
        return doc

    async def update(self, user: User, folder_id: str, changes: dict[str, Any]) -> dict[str, Any]:
        """`changes` may contain "name" (rename) and/or "parent_id" (move; None = top level)."""
        doc = await self.owned(user, folder_id)
        name = clean_folder_name(changes["name"]) if changes.get("name") else doc["name"]

        parent_oid = doc["parent_id"]
        ancestors = doc["ancestors"]
        if "parent_id" in changes:
            target_id = changes["parent_id"]
            target = await self.owned(user, target_id) if target_id else None
            # A folder can't go inside itself or one of its own sub-folders (that makes a loop).
            if target and (target["_id"] == doc["_id"] or doc["_id"] in target["ancestors"]):
                raise AppError("INVALID_MOVE", "A folder can't be moved into itself.", 400)
            parent_oid = target["_id"] if target else None
            ancestors = [*target["ancestors"], target["_id"]] if target else []

        if await self.folders.name_taken(str(user.id), parent_oid, name.lower(), doc["_id"]):
            raise _name_taken()

        try:
            await self.folders.update(
                doc["_id"],
                {
                    "name": name,
                    "name_lower": name.lower(),
                    "parent_id": parent_oid,
                    "ancestors": ancestors,
                    "updated_at": datetime.now(UTC),
                },
            )
        except DuplicateKeyError as exc:
            raise _name_taken() from exc

        if ancestors != doc["ancestors"]:
            # Moved: every sub-folder's path changes too (keep the part below this folder).
            for child in await self.folders.descendants(doc["_id"]):
                below = child["ancestors"][child["ancestors"].index(doc["_id"]) + 1 :]
                await self.folders.update(
                    child["_id"], {"ancestors": [*ancestors, doc["_id"], *below]}
                )
            await self._log(
                user, "folder.move", doc, {"to": str(parent_oid) if parent_oid else None}
            )
        if name != doc["name"]:
            await self._log(user, "folder.rename", doc, {"from": doc["name"], "to": name})
        return await self.owned(user, folder_id)

    async def trash(self, user: User, folder_id: str) -> None:
        """Move the folder, its sub-folders and all files inside them to the trash."""
        doc = await self.owned(user, folder_id)
        inside = [
            f["_id"] for f in await self.folders.descendants(doc["_id"]) if f["status"] == "active"
        ]
        now = datetime.now(UTC)
        await self.folders.update(
            doc["_id"], {"status": "trashed", "trashed_at": now, "trashed_directly": True}
        )
        await self.folders.update_many(
            inside, {"status": "trashed", "trashed_at": now, "trashed_directly": False}
        )
        await self.files.update_many(
            {
                "owner_id": str(user.id),
                "folder_id": {"$in": [doc["_id"], *inside]},
                "status": "active",
            },
            {"$set": {"status": "trashed", "trashed_at": now, "trashed_with_folder": True}},
        )
        await self._log(user, "folder.trash", doc, {"name": doc["name"]})

    async def restore(self, user: User, folder_id: str) -> dict[str, Any]:
        doc = await self.owned(user, folder_id, active=False)
        if doc["status"] != "trashed":
            raise AppError("NOT_IN_TRASH", "This folder is not in the trash.", 400)
        if doc["parent_id"]:
            parent = await self.folders.get(doc["parent_id"])
            if parent is None or parent["status"] != "active":
                raise AppError(
                    "PARENT_IN_TRASH", "Restore the folder that contained it first.", 409
                )
        if await self.folders.name_taken(
            str(user.id), doc["parent_id"], doc["name_lower"], doc["_id"]
        ):
            raise _name_taken()

        # Bring back the sub-folders and files that were trashed together with it.
        inside = [
            f["_id"]
            for f in await self.folders.descendants(doc["_id"])
            if f["status"] == "trashed" and not f.get("trashed_directly")
        ]
        restored = {"status": "active", "trashed_at": None, "trashed_directly": False}
        await self.folders.update(doc["_id"], restored)
        await self.folders.update_many(inside, restored)
        await self.files.update_many(
            {
                "owner_id": str(user.id),
                "folder_id": {"$in": [doc["_id"], *inside]},
                "status": "trashed",
                "trashed_with_folder": True,
            },
            {"$set": {"status": "active", "trashed_at": None, "trashed_with_folder": False}},
        )
        await self._log(user, "folder.restore", doc, {"name": doc["name"]})
        return await self.owned(user, folder_id)

    async def _log(
        self, user: User, action: str, doc: dict[str, Any], details: dict[str, Any]
    ) -> None:
        await self.activity.log(
            self.request,
            user,
            action,
            resource_type="folder",
            resource_id=str(doc["_id"]),
            details=details,
        )
