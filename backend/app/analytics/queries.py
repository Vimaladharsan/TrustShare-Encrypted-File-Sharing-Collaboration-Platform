"""Shared building blocks for admin analytics (Task 5) and reports (Task 4).

All numbers come from the real records: file metadata (MongoDB `files` + `vault_files`), activity
(`activity_logs`), alerts (`security_events`), accounts and shares (PostgreSQL).
Admins see file IDs, types and sizes – never file names (privacy rule).
"""

import csv
import io
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
from fastapi.responses import Response
from pymongo.asynchronous.database import AsyncDatabase
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.services.analytics_service import CATEGORIES, Period
from app.services.file_validation import ALLOWED_TYPES, extension_of

UPLOAD_ACTIONS = ["file.upload", "vault.file_added"]
REJECTED_UPLOAD_ACTIONS = ["file.upload_rejected", "vault.upload_rejected"]
DOWNLOAD_ACTIONS = ["file.download", "vault.file_downloaded"]


@dataclass
class Filters:
    """The brief's filters: date range, user, file type, activity type (+ file ID for reports)."""

    period: Period
    user_id: str | None = None
    file_type: str | None = None  # category: document, spreadsheet, presentation, image, text
    activity_type: str | None = None
    file_id: str | None = None

    def activity_match(self, actions: list[str]) -> dict[str, Any]:
        match: dict[str, Any] = {"action": {"$in": actions}, "created_at": self.period.current()}
        if self.user_id:
            match["user_id"] = self.user_id
        if self.activity_type:
            match["activity_type"] = self.activity_type
        if self.file_id:
            match["file_id"] = self.file_id
        return match


def category_of_extension(extension: str | None) -> str:
    file_type = ALLOWED_TYPES.get((extension or "").lower())
    return file_type.category if file_type else "other"


def extension_from(details: dict[str, Any]) -> str | None:
    """The file type of an activity – from the stored extension, or the name's extension
    (only the extension is kept; the name itself is never returned to admins)."""
    if details.get("extension"):
        return str(details["extension"]).lower()
    name = details.get("file_name")
    return extension_of(name) if name else None


async def file_meta(db: AsyncDatabase, file_ids: set[str]) -> dict[str, dict[str, Any]]:
    """{file_id: {extension, category, owner_id, size_bytes, vault}} – no names."""
    oids = []
    for value in file_ids:
        try:
            oids.append(ObjectId(value))
        except (InvalidId, TypeError):
            continue
    found: dict[str, dict[str, Any]] = {}
    projection = {"extension": 1, "category": 1, "owner_id": 1, "size_bytes": 1}
    for collection, vault in (("files", False), ("vault_files", True)):
        async for doc in db[collection].find({"_id": {"$in": oids}}, projection):
            found[str(doc["_id"])] = {
                "extension": doc.get("extension"),
                "category": doc.get("category") or category_of_extension(doc.get("extension")),
                "owner_id": doc.get("owner_id"),
                "size_bytes": doc.get("size_bytes", 0),
                "vault": vault,
            }
    return found


async def people(session: AsyncSession, user_ids: set[str | None]) -> dict[str, dict[str, Any]]:
    """{user_id: {email, full_name, quota_bytes, role}}."""
    ids = []
    for value in user_ids:
        try:
            ids.append(uuid.UUID(str(value)))
        except (ValueError, TypeError):
            continue
    if not ids:
        return {}
    users = (await session.scalars(select(User).where(User.id.in_(ids)))).all()
    return {
        str(u.id): {
            "email": u.email,
            "full_name": u.full_name,
            "quota_bytes": u.storage_quota_bytes,
            "role": u.role.name,
        }
        for u in users
    }


def empty_days(period: Period, *keys: str) -> dict[Any, dict[str, Any]]:
    return {day: {"date": day, **dict.fromkeys(keys, 0)} for day in period.days}


def category_keys() -> list[str]:
    return [*CATEGORIES, "other"]


def _csv_safe(value: Any) -> str:
    text = "" if value is None else str(value)
    if isinstance(value, datetime):
        text = value.astimezone(UTC).isoformat(timespec="seconds")
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


def csv_response(name: str, columns: list[str], rows: list[dict[str, Any]]) -> Response:
    """CSV download (formula-injection safe, UTF-8 with BOM for Excel)."""
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(columns)
    for row in rows:
        writer.writerow([_csv_safe(row.get(column)) for column in columns])
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M")
    return Response(
        content="﻿" + out.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="trustshare-{name}-{stamp}.csv"'},
    )
