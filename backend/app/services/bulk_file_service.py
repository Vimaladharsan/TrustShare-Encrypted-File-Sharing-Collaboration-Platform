"""Actions on several files ticked in My Files: move, trash, or download them as one ZIP.

Move and trash handle each file on its own with the same rules as the single-file actions, so
one problem doesn't stop the rest – the result says how many succeeded and which failed and why
(same shape as the trash's bulk actions).

The ZIP is built while it is being sent: each file is decrypted chunk by chunk (every GCM tag is
checked) straight into the archive, so a decrypted file is never written to disk and memory use
stays at about one chunk, however many files are selected.
"""

import zipfile
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from fastapi import Request
from pymongo.asynchronous.database import AsyncDatabase

from app.core.config import get_settings
from app.core.errors import AppError
from app.models import User
from app.services.file_service import FileService
from app.services.trash_service import _attempt, _empty_result
from app.storage.secure_store import SecureFileStore

# Already-compressed formats (PDF, Office, images) are stored as they are; only text is deflated.
COMPRESSIBLE = {"txt", "csv"}


class _Sink:
    """Write-only buffer for zipfile. The archive is written into it and the response takes the
    bytes out after every chunk (zipfile supports such non-seekable outputs)."""

    def __init__(self) -> None:
        self._parts: list[bytes] = []

    def write(self, data: bytes) -> int:
        self._parts.append(bytes(data))
        return len(data)

    def flush(self) -> None:
        pass

    def close(self) -> None:
        pass

    def drain(self) -> bytes:
        data = b"".join(self._parts)
        self._parts.clear()
        return data


def _unique_names(docs: list[dict[str, Any]]) -> list[str]:
    """Two selected files may share a name (different folders) – the second becomes "name (2)"."""
    seen: set[str] = set()
    names = []
    for doc in docs:
        name = doc["original_name"]
        stem, dot, ext = name.rpartition(".")
        if not dot:
            stem, ext = name, ""
        candidate, n = name, 2
        while candidate.lower() in seen:
            candidate = f"{stem} ({n}).{ext}" if ext else f"{stem} ({n})"
            n += 1
        seen.add(candidate.lower())
        names.append(candidate)
    return names


def zip_filename(count: int) -> str:
    return f"TrustShare-{count}-files-{datetime.now(UTC):%Y%m%d-%H%M}.zip"


class BulkFileService:
    def __init__(self, db: AsyncDatabase, storage: SecureFileStore, request: Request) -> None:
        self.files = FileService(db, storage, request)
        self.storage = storage
        self.request = request

    async def move(self, user: User, file_ids: list[str], folder_id: str | None) -> dict:
        await self.files._target_folder(user, folder_id)  # unknown destination → 404 for all
        result = _empty_result()
        for file_id in dict.fromkeys(file_ids):
            await _attempt(
                result, "file", file_id, self.files.update(user, file_id, {"folder_id": folder_id})
            )
        return result

    async def trash(self, user: User, file_ids: list[str]) -> dict:
        result = _empty_result()
        for file_id in dict.fromkeys(file_ids):
            await _attempt(result, "file", file_id, self.files.trash(user, file_id))
        return result

    async def download_zip(self, user: User, file_ids: list[str]) -> AsyncIterator[bytes]:
        """Checks everything before the first byte is sent (all files must be the user's own,
        active files, within the limits), records the downloads, then returns the ZIP stream."""
        settings = get_settings()
        ids = list(dict.fromkeys(file_ids))
        if len(ids) > settings.zip_max_files:
            raise AppError(
                "TOO_MANY_FILES",
                f"Select at most {settings.zip_max_files} files for one ZIP.",
                400,
            )
        docs = [await self.files.owned(user, file_id) for file_id in ids]
        total = sum(doc["size_bytes"] for doc in docs)
        if total > settings.zip_max_bytes:
            raise AppError(
                "ZIP_TOO_LARGE",
                f"The selected files are larger than {settings.zip_max_mb} MB together. "
                "Download them in smaller groups.",
                413,
            )

        # One record per file keeps every file's history, reports and analytics correct;
        # the summary record is what the "excessive downloads" rule counts (one request = once).
        for doc in docs:
            await self.files.activity.log(
                self.request,
                user,
                "file.download",
                resource_type="file",
                resource_id=str(doc["_id"]),
                details={
                    "file_name": doc["original_name"],
                    "owner_id": doc["owner_id"],
                    "via": "zip",
                },
            )
        await self.files.activity.log(
            self.request,
            user,
            "file.download_zip",
            details={"count": len(docs), "size_bytes": total},
        )
        return self._stream(docs)

    async def _stream(self, docs: list[dict[str, Any]]) -> AsyncIterator[bytes]:
        sink = _Sink()
        with zipfile.ZipFile(sink, "w") as archive:
            for doc, name in zip(docs, _unique_names(docs), strict=True):
                info = zipfile.ZipInfo(name, date_time=_zip_time(doc["created_at"]))
                info.file_size = doc["size_bytes"]
                info.compress_type = (
                    zipfile.ZIP_DEFLATED if doc["extension"] in COMPRESSIBLE else zipfile.ZIP_STORED
                )
                with archive.open(info, "w") as entry:
                    async for chunk in await self.storage.open(doc):
                        entry.write(chunk)
                        if data := sink.drain():
                            yield data
                if data := sink.drain():
                    yield data
        yield sink.drain()  # the archive's table of contents, written on close


def _zip_time(when: datetime) -> tuple[int, int, int, int, int, int]:
    when = max(when, datetime(1980, 1, 1, tzinfo=when.tzinfo))  # ZIP dates start in 1980
    return (when.year, when.month, when.day, when.hour, when.minute, when.second)
