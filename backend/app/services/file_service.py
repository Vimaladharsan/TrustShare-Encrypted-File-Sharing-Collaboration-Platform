"""File upload, listing and access rules. All file decisions live here.

Upload pipeline (docs/architecture.md §3.4 and §8.2):
  permission (route) → clean name → extension allow-list → quota → stream to a temp file in
  1 MB chunks while counting size and computing SHA-256 → magic bytes / Office structure →
  duplicate check → encrypt with a new AES-256 key and store in the private bucket (SecureFileStore)
  → metadata in MongoDB → activity log
"""

import asyncio
import hashlib
import logging
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from bson import ObjectId
from fastapi import Request, UploadFile
from pymongo.asynchronous.database import AsyncDatabase

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.permissions import Perm
from app.models import User
from app.repositories.file_repository import FileRepository
from app.repositories.folder_repository import FolderRepository
from app.services.activity_service import ActivityService
from app.services.file_validation import (
    ALLOWED_EXTENSIONS_TEXT,
    ALLOWED_TYPES,
    PREVIEWABLE,
    clean_filename,
    content_matches,
    extension_of,
    office_structure_ok,
)
from app.storage.local import CHUNK_SIZE
from app.storage.secure_store import SecureFileStore

logger = logging.getLogger(__name__)


def _not_found() -> AppError:
    # Same answer for "doesn't exist" and "not yours": never confirm another user's file exists.
    return AppError("FILE_NOT_FOUND", "File not found.", 404)


class FileService:
    def __init__(self, db: AsyncDatabase, storage: SecureFileStore, request: Request) -> None:
        self.files = FileRepository(db)
        self.folders = FolderRepository(db)
        self.activity = ActivityService(db)
        self.storage = storage
        self.request = request

    # ---------- upload ----------

    async def upload(
        self, user: User, upload: UploadFile, folder_id: str | None, allow_duplicate: bool
    ) -> dict[str, Any]:
        name = clean_filename(upload.filename)
        extension = extension_of(name)
        try:
            folder_oid = await self._target_folder(user, folder_id)
            if not name or extension not in ALLOWED_TYPES:
                raise AppError(
                    "UNSUPPORTED_FILE_TYPE",
                    f"This file type is not allowed. Allowed: {ALLOWED_EXTENSIONS_TEXT}.",
                    415,
                )
            used = await self.files.used_bytes(str(user.id))
            if used >= user.storage_quota_bytes:
                raise self._quota_error()

            temp = self.storage.temp_path(uuid.uuid4().hex)
            try:
                size, sha256 = await self._receive(upload, temp, extension)
                if used + size > user.storage_quota_bytes:
                    raise self._quota_error()
                if not await asyncio.to_thread(office_structure_ok, extension, temp):
                    raise self._type_mismatch()
                if not allow_duplicate and await self.files.find_duplicate(
                    str(user.id), sha256, folder_oid
                ):
                    raise AppError(
                        "DUPLICATE_FILE", "You already have an identical file here.", 409
                    )

                # Encrypt with a fresh key and store under a random name (never the filename).
                file_oid = ObjectId()
                stored = await self.storage.store(str(file_oid), user.id, temp)
            finally:
                await asyncio.to_thread(temp.unlink, missing_ok=True)
        except AppError as exc:
            await self.activity.log(
                self.request,
                user,
                "file.upload_rejected",
                resource_type="file",
                status="failure",
                details={"file_name": name, "reason": exc.code},
            )
            raise

        now = datetime.now(UTC)
        file_type = ALLOWED_TYPES[extension]
        doc = {
            "_id": file_oid,
            "owner_id": str(user.id),
            "folder_id": folder_oid,
            "original_name": name,
            "name_lower": name.lower(),
            "extension": extension,
            "mime_type": file_type.mime_type,
            "category": file_type.category,
            "size_bytes": size,
            "sha256": sha256,
            **stored,  # storage_backend, storage_key, encryption info (no key material)
            "version": 1,
            "status": "active",
            "trashed_at": None,
            "created_at": now,
            "updated_at": now,
        }
        try:
            await self.files.insert(doc)
        except Exception:
            await self.storage.delete(doc)  # don't leave an encrypted object without metadata
            raise
        await self.activity.log(
            self.request,
            user,
            "file.upload",
            resource_type="file",
            resource_id=str(doc["_id"]),
            details={"file_name": name, "size_bytes": size},
        )
        logger.info("File uploaded: %s (%d bytes) by %s", doc["_id"], size, user.id)
        return doc

    async def _receive(self, upload: UploadFile, temp: Path, extension: str) -> tuple[int, str]:
        """Copy the upload to a temp file in 1 MB chunks: count the size (stop at the limit),
        compute the SHA-256 fingerprint, and check the first bytes – all in one pass."""
        max_bytes = get_settings().max_upload_bytes
        digest = hashlib.sha256()
        size = 0
        with temp.open("wb") as out:  # noqa: ASYNC230 – writes run in a worker thread below
            while chunk := await upload.read(CHUNK_SIZE):
                if size == 0 and not content_matches(extension, chunk[:2048]):
                    raise self._type_mismatch()
                size += len(chunk)
                if size > max_bytes:
                    raise AppError(
                        "FILE_TOO_LARGE",
                        f"File exceeds the {get_settings().max_upload_mb} MB limit.",
                        413,
                    )
                digest.update(chunk)
                await asyncio.to_thread(out.write, chunk)
        if size == 0:
            raise AppError("EMPTY_FILE", "The file is empty.", 400)
        return size, digest.hexdigest()

    @staticmethod
    def _type_mismatch() -> AppError:
        return AppError(
            "UNSUPPORTED_FILE_TYPE",
            "The file's content does not match its extension.",
            415,
        )

    @staticmethod
    def _quota_error() -> AppError:
        return AppError("QUOTA_EXCEEDED", "Not enough storage space left.", 413)

    # ---------- reading ----------

    async def get_for_read(self, user: User, file_id: str) -> dict[str, Any]:
        """Owner can read; Admins (file:read_all) can read anyone's file. Others get 404."""
        doc = await self.files.get(file_id)
        if doc is None:
            raise _not_found()
        if doc["owner_id"] != str(user.id) and Perm.FILE_READ_ALL not in user.permission_codes:
            raise _not_found()
        return doc

    async def download(self, user: User, file_id: str) -> tuple[dict[str, Any], AsyncIterator]:
        doc = await self.get_for_read(user, file_id)
        await self.activity.log(
            self.request,
            user,
            "file.download",
            resource_type="file",
            resource_id=file_id,
            details={"file_name": doc["original_name"]},
        )
        return doc, await self.storage.open(doc)

    async def preview(self, user: User, file_id: str) -> tuple[dict[str, Any], AsyncIterator]:
        """Same access rules as download, but only for types the browser can display."""
        doc = await self.get_for_read(user, file_id)
        if doc["extension"] not in PREVIEWABLE:
            raise AppError(
                "PREVIEW_NOT_SUPPORTED", "This file type can't be previewed. Download it.", 415
            )
        await self.activity.log(
            self.request,
            user,
            "file.preview",
            resource_type="file",
            resource_id=file_id,
            details={"file_name": doc["original_name"]},
        )
        return doc, await self.storage.open(doc)

    # ---------- organising: rename, move, trash, restore, delete ----------

    async def _target_folder(self, user: User, folder_id: str | None) -> ObjectId | None:
        """The folder a file goes into (must be the user's own, active folder). None = top level."""
        if not folder_id:
            return None
        folder = await self.folders.get_active_owned(str(user.id), folder_id)
        if folder is None:
            raise AppError("FOLDER_NOT_FOUND", "Folder not found.", 404)
        return folder["_id"]

    async def owned(
        self, user: User, file_id: str, status: str | None = "active"
    ) -> dict[str, Any]:
        """Only the owner may change a file – not even an Admin can alter someone else's."""
        doc = await self.files.get(file_id)
        if doc is None or doc["owner_id"] != str(user.id):
            raise _not_found()
        if status and doc["status"] != status:
            raise _not_found()
        return doc

    async def update(self, user: User, file_id: str, changes: dict[str, Any]) -> dict[str, Any]:
        """`changes` may contain "name" (rename) and/or "folder_id" (move; None = top level)."""
        doc = await self.owned(user, file_id)
        updates: dict[str, Any] = {}
        if changes.get("name"):
            name = clean_filename(changes["name"])
            # Keep the extension: it was checked against the file's real content at upload.
            if extension_of(name) != doc["extension"]:
                raise AppError(
                    "EXTENSION_CHANGE_NOT_ALLOWED",
                    f"The name must still end in .{doc['extension']}.",
                    400,
                )
            updates |= {"original_name": name, "name_lower": name.lower()}
        if "folder_id" in changes:
            updates["folder_id"] = await self._target_folder(user, changes["folder_id"])
        if not updates:
            return doc

        updates["updated_at"] = datetime.now(UTC)
        await self.files.update(doc["_id"], updates)
        if "original_name" in updates:
            await self._log(
                user,
                "file.rename",
                doc,
                {"from": doc["original_name"], "to": updates["original_name"]},
            )
        if "folder_id" in updates and updates["folder_id"] != doc.get("folder_id"):
            await self._log(user, "file.move", doc, {"file_name": doc["original_name"]})
        return await self.owned(user, file_id)

    async def trash(self, user: User, file_id: str) -> None:
        doc = await self.owned(user, file_id)
        now = datetime.now(UTC)
        await self.files.update(
            doc["_id"],
            {
                "status": "trashed",
                "trashed_at": now,
                "trashed_with_folder": False,
                "updated_at": now,
            },
        )
        await self._log(user, "file.trash", doc, {"file_name": doc["original_name"]})

    async def restore(self, user: User, file_id: str) -> dict[str, Any]:
        doc = await self.owned(user, file_id, status="trashed")
        folder_id = doc.get("folder_id")
        if folder_id:
            folder = await self.folders.get(folder_id)
            if folder is None or folder["status"] != "active":
                folder_id = None  # its folder is gone or in the trash: restore to the top level
        await self.files.update(
            doc["_id"],
            {
                "status": "active",
                "trashed_at": None,
                "trashed_with_folder": False,
                "folder_id": folder_id,
                "updated_at": datetime.now(UTC),
            },
        )
        await self._log(user, "file.restore", doc, {"file_name": doc["original_name"]})
        return await self.owned(user, file_id)

    async def delete_forever(self, user: User, file_id: str) -> None:
        """Remove the bytes from storage and the metadata from MongoDB. Cannot be undone."""
        doc = await self.owned(user, file_id, status=None)
        await self.storage.delete(doc)  # encrypted object + its key
        await self.files.delete(doc["_id"])
        await self._log(
            user,
            "file.delete",
            doc,
            {"file_name": doc["original_name"], "size_bytes": doc["size_bytes"]},
        )

    async def _log(
        self, user: User, action: str, doc: dict[str, Any], details: dict[str, Any]
    ) -> None:
        await self.activity.log(
            self.request,
            user,
            action,
            resource_type="file",
            resource_id=str(doc["_id"]),
            details=details,
        )
