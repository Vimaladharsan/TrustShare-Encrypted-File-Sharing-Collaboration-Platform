"""Bulk trash actions: restore or permanently delete several items, restore all, empty trash.

Each item is handled on its own, so one problem (e.g. a name clash on restore) doesn't stop the
rest; the result says how many succeeded and which ones failed and why.
"""

from typing import Any

from fastapi import Request
from pymongo.asynchronous.database import AsyncDatabase

from app.core.errors import AppError
from app.core.permissions import Perm
from app.models import User
from app.repositories.file_repository import FileRepository
from app.repositories.folder_repository import FolderRepository
from app.services.file_service import FileService
from app.services.folder_service import FolderService
from app.storage.local import LocalStorage


class TrashService:
    def __init__(self, db: AsyncDatabase, storage: LocalStorage, request: Request) -> None:
        self.files = FileService(db, storage, request)
        self.folders = FolderService(db, request, storage)
        self.file_repo = FileRepository(db)
        self.folder_repo = FolderRepository(db)

    # ---------- what's in the trash ----------

    async def all_ids(self, user: User) -> tuple[list[str], list[str]]:
        """(file ids, folder ids) of everything the user sees in their trash."""
        files, _ = await self.file_repo.list_owned(
            str(user.id),
            trashed=True,
            search=None,
            category=None,
            sort="date",
            order="desc",
            limit=10_000,
            offset=0,
        )
        folders = await self.folder_repo.list_trashed(str(user.id))
        return [str(f["_id"]) for f in files], [str(f["_id"]) for f in folders]

    # ---------- bulk actions ----------

    async def restore(self, user: User, file_ids: list[str], folder_ids: list[str]) -> dict:
        _require_folder_permission(user, folder_ids)
        result = _empty_result()
        # Parents before children, so a sub-folder trashed on its own can return into its parent.
        folders = [await self.folder_repo.get(fid) for fid in folder_ids]
        ordered = sorted(
            zip(folder_ids, folders, strict=True),
            key=lambda pair: len(pair[1]["ancestors"]) if pair[1] else 0,
        )
        for folder_id, _ in ordered:
            await _attempt(result, "folder", folder_id, self.folders.restore(user, folder_id))
        for file_id in file_ids:
            await _attempt(result, "file", file_id, self.files.restore(user, file_id))
        return result

    async def delete(self, user: User, file_ids: list[str], folder_ids: list[str]) -> dict:
        _require_folder_permission(user, folder_ids)
        result = _empty_result()
        # Files first, then folders from the top down. A folder deletes everything inside it,
        # so a selected item may already be gone by the time we reach it – that counts as done.
        for file_id in file_ids:
            await _attempt(result, "file", file_id, self._delete_trashed_file(user, file_id))
        folders = {fid: await self.folder_repo.get(fid) for fid in folder_ids}
        for folder_id in sorted(
            folder_ids, key=lambda fid: len(folders[fid]["ancestors"]) if folders[fid] else 0
        ):
            original = folders[folder_id]
            owned = original is not None and original["owner_id"] == str(user.id)
            if owned and await self.folder_repo.get(folder_id) is None:
                result["succeeded"] += 1  # removed together with a parent folder above
                continue
            await _attempt(
                result, "folder", folder_id, self.folders.delete_forever(user, folder_id)
            )
        return result

    async def restore_all(self, user: User) -> dict:
        file_ids, folder_ids = await self.all_ids(user)
        return await self.restore(user, file_ids, folder_ids)

    async def empty(self, user: User) -> dict:
        file_ids, folder_ids = await self.all_ids(user)
        return await self.delete(user, file_ids, folder_ids)

    async def _delete_trashed_file(self, user: User, file_id: str) -> None:
        await self.files.owned(user, file_id, status="trashed")  # only items in the trash
        await self.files.delete_forever(user, file_id)


def _require_folder_permission(user: User, folder_ids: list[str]) -> None:
    if folder_ids and Perm.FOLDER_MANAGE not in user.permission_codes:
        raise AppError("FORBIDDEN", "You don't have permission to do this.", status_code=403)


def _empty_result() -> dict[str, Any]:
    return {"succeeded": 0, "failed": []}


async def _attempt(result: dict[str, Any], kind: str, item_id: str, action: Any) -> None:
    try:
        await action
        result["succeeded"] += 1
    except AppError as exc:
        result["failed"].append(
            {"id": item_id, "type": kind, "code": exc.code, "message": exc.message}
        )
