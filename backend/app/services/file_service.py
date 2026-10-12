"""File upload, listing and access rules. All file decisions live here.

Upload pipeline (docs/architecture.md §3.4):
  permission (route) → clean name → extension allow-list → quota → stream to a temp file in
  1 MB chunks while counting size and computing SHA-256 → magic bytes / Office structure →
  duplicate check → move to storage under a random key → metadata in MongoDB → activity log
"""

import asyncio
import hashlib
import logging
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import Request, UploadFile
from pymongo.asynchronous.database import AsyncDatabase

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.permissions import Perm
from app.models import User
from app.repositories.file_repository import FileRepository
from app.services.activity_service import ActivityService
from app.services.file_validation import (
    ALLOWED_EXTENSIONS_TEXT,
    ALLOWED_TYPES,
    clean_filename,
    content_matches,
    extension_of,
    office_structure_ok,
)
from app.storage.local import CHUNK_SIZE, LocalStorage

logger = logging.getLogger(__name__)


def _not_found() -> AppError:
    # Same answer for "doesn't exist" and "not yours": never confirm another user's file exists.
    return AppError("FILE_NOT_FOUND", "File not found.", 404)


class FileService:
    def __init__(self, db: AsyncDatabase, storage: LocalStorage, request: Request) -> None:
        self.files = FileRepository(db)
        self.activity = ActivityService(db)
        self.storage = storage
        self.request = request

    # ---------- upload ----------

    async def upload(self, user: User, upload: UploadFile, allow_duplicate: bool) -> dict[str, Any]:
        name = clean_filename(upload.filename)
        extension = extension_of(name)
        try:
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
                    str(user.id), sha256, None
                ):
                    raise AppError(
                        "DUPLICATE_FILE", "You already have an identical file here.", 409
                    )

                # Random storage name: the user's filename never becomes a path on disk.
                storage_key = f"{user.id}/{uuid.uuid4()}"
                await self.storage.save(storage_key, temp)
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
        doc = await self.files.insert(
            {
                "owner_id": str(user.id),
                "folder_id": None,
                "original_name": name,
                "name_lower": name.lower(),
                "extension": extension,
                "mime_type": file_type.mime_type,
                "category": file_type.category,
                "size_bytes": size,
                "sha256": sha256,
                "storage_backend": "local",
                "storage_key": storage_key,
                "version": 1,
                "status": "active",
                "trashed_at": None,
                "encryption": None,  # filled in from Milestone 2 (AES-256-GCM)
                "created_at": now,
                "updated_at": now,
            }
        )
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
        return doc, self.storage.open(doc["storage_key"])
