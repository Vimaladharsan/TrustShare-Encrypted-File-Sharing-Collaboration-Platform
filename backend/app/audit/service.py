"""Append-only, hash-chained audit log.

append():  next seq = last seq + 1, prev_hash = last hash, hash = SHA-256(prev_hash + entry).
           A unique index on `seq` means two simultaneous writers can't both take the same place:
           the loser gets a duplicate-key error and simply retries on top of the new last entry –
           so the chain never forks and no lock is needed.
verify():  walks the chain in order and re-computes every hash.
There is deliberately no API to edit or delete entries; the chain makes any change detectable.
"""

import csv
import io
import logging
import re
import uuid
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pymongo import ASCENDING, DESCENDING, IndexModel
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import DuplicateKeyError

from app.activity_monitoring.models import activity_type_of
from app.audit.models import GENESIS_HASH, describe, entry_hash
from app.audit.schemas import AuditLogEntry, AuditLogPage, AuditVerification
from app.core.config import get_settings
from app.core.errors import AppError
from app.models import User

logger = logging.getLogger(__name__)

APPEND_RETRIES = 20
EXPORT_LIMIT = 10_000
CSV_COLUMNS = [
    "seq",
    "time_utc",
    "user_id",
    "username",
    "activity_type",
    "action",
    "file_id",
    "description",
    "status",
    "ip_address",
    "hash",
]
_indexed: set[str] = set()


def _csv_safe(value: str) -> str:
    """No spreadsheet formula injection (a cell starting with = + - @ runs as a formula)."""
    return "'" + value if value[:1] in ("=", "+", "-", "@", "\t", "\r") else value


class AuditService:
    def __init__(self, db: AsyncDatabase, collection: str | None = None) -> None:
        self.collection = db[collection or get_settings().audit_collection]

    async def _ensure_indexes(self) -> None:
        if self.collection.name in _indexed:
            return
        await self.collection.create_indexes(
            [
                IndexModel([("seq", ASCENDING)], name="seq_unique", unique=True),
                IndexModel([("user_id", ASCENDING), ("seq", DESCENDING)], name="user_seq"),
                IndexModel([("file_id", ASCENDING), ("seq", DESCENDING)], name="file_seq"),
                IndexModel([("created_at", DESCENDING)], name="created"),
                IndexModel([("source_activity_id", ASCENDING)], name="source", sparse=True),
            ]
        )
        _indexed.add(self.collection.name)

    # ---------- write ----------

    async def append(
        self,
        activity: dict[str, Any],
        user: User | None,
        *,
        imported: bool = False,
    ) -> dict[str, Any]:
        """Add one activity to the chain. `activity` is an activity_logs record."""
        await self._ensure_indexes()
        details = activity.get("details") or {}
        created = activity["created_at"]
        created = created.replace(microsecond=created.microsecond // 1000 * 1000)  # Mongo keeps ms
        entry: dict[str, Any] = {
            "log_id": str(uuid.uuid4()),
            "user_id": activity.get("user_id"),
            "username": (
                user.full_name
                if user
                else activity.get("username") or details.get("email") or activity.get("actor_email")
            ),
            "activity_type": activity.get("activity_type") or activity_type_of(activity["action"]),
            "action": activity["action"],
            "file_id": activity.get("file_id"),
            "description": describe(activity["action"], details),
            "status": activity.get("status", "success"),
            "ip_address": activity.get("ip_address"),
            "created_at": created,
        }
        if imported:
            entry["imported"] = True
            entry["source_activity_id"] = activity.get("_id")
        for _ in range(APPEND_RETRIES):
            last = await self.collection.find_one({}, {"seq": 1, "hash": 1}, sort=[("seq", -1)])
            entry["seq"] = last["seq"] + 1 if last else 1
            entry["prev_hash"] = last["hash"] if last else GENESIS_HASH
            entry["hash"] = entry_hash(entry["prev_hash"], entry)
            try:
                await self.collection.insert_one(entry)
                return entry
            except DuplicateKeyError:
                entry.pop("_id", None)  # someone else took this seq – retry on top of theirs
        raise RuntimeError("Could not append to the audit log (too much contention)")

    # ---------- read ----------

    async def page(self, match: dict[str, Any], limit: int, offset: int) -> AuditLogPage:
        await self._ensure_indexes()
        total = await self.collection.count_documents(match)
        cursor = self.collection.find(match).sort("seq", -1).skip(offset).limit(limit)
        return AuditLogPage(
            items=[_entry(e) for e in await cursor.to_list(length=limit)], total=total
        )

    async def csv(self, match: dict[str, Any]) -> tuple[str, int]:
        cursor = self.collection.find(match).sort("seq", -1).limit(EXPORT_LIMIT)
        entries = await cursor.to_list(length=EXPORT_LIMIT)
        out = io.StringIO()
        writer = csv.writer(out)
        writer.writerow(CSV_COLUMNS)
        for e in entries:
            row = [
                str(e["seq"]),
                e["created_at"].astimezone(UTC).isoformat(timespec="seconds"),
                e.get("user_id") or "",
                e.get("username") or "",
                e.get("activity_type") or "",
                e["action"],
                e.get("file_id") or "",
                e.get("description") or "",
                e.get("status") or "",
                e.get("ip_address") or "",
                e["hash"],
            ]
            writer.writerow([_csv_safe(value) for value in row])
        return out.getvalue(), len(entries)

    async def verify(self) -> AuditVerification:
        """Re-compute the whole chain, oldest first."""
        previous, expected_seq, checked = GENESIS_HASH, 1, 0
        async for e in self.collection.find({}).sort("seq", 1):
            if e["seq"] != expected_seq:
                return _broken(checked, expected_seq - 1, expected_seq, "an entry is missing")
            if e["prev_hash"] != previous:
                return _broken(
                    checked, e["seq"] - 1, e["seq"], "the link to the previous entry is broken"
                )
            if entry_hash(previous, e) != e["hash"]:
                return _broken(checked, e["seq"] - 1, e["seq"], "the entry was changed")
            previous, expected_seq, checked = e["hash"], expected_seq + 1, checked + 1
        return AuditVerification(valid=True, checked=checked, last_seq=expected_seq - 1 or None)


def build_filter(
    *,
    user_id: str | None = None,
    activity_type: str | None = None,
    file_id: str | None = None,
    status: str | None = None,
    search: str | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    tz: str = "UTC",
    since: datetime | None = None,
    until: datetime | None = None,
) -> dict[str, Any]:
    """MongoDB filter for the brief's audit filters: user, activity type, file ID, status, dates –
    plus an optional exact time window (since / until), e.g. 30 minutes around an alert."""
    match: dict[str, Any] = {}
    if user_id:
        match["user_id"] = user_id
    if activity_type:
        match["activity_type"] = activity_type
    if file_id:
        match["file_id"] = file_id
    if status:
        match["status"] = status
    if search:
        pattern = {"$regex": re.escape(search), "$options": "i"}  # literal text, not a regex
        match["$or"] = [
            {"username": pattern},
            {"ip_address": pattern},
            {"action": pattern},
            {"description": pattern},
        ]
    if from_date or to_date:
        try:
            zone = ZoneInfo(tz)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise AppError("INVALID_TIMEZONE", "Unknown time zone.", 400) from exc
        when: dict[str, datetime] = {}
        if from_date:
            when["$gte"] = datetime.combine(from_date, time.min, zone).astimezone(UTC)
        if to_date:
            end = datetime.combine(to_date + timedelta(days=1), time.min, zone).astimezone(UTC)
            when["$lt"] = end
        if from_date and to_date and from_date > to_date:
            raise AppError("INVALID_RANGE", "The start date must be before the end date.", 400)
        match["created_at"] = when
    if since or until:
        if since and until and since > until:
            raise AppError("INVALID_RANGE", "The start time must be before the end time.", 400)
        window = match.setdefault("created_at", {})
        if since:
            window["$gte"] = max(since, window.get("$gte", since))
        if until:
            window["$lte"] = until
    return match


def _broken(checked: int, last_good: int, seq: int, reason: str) -> AuditVerification:
    logger.error("Audit log chain broken at seq %s: %s", seq, reason)
    return AuditVerification(
        valid=False,
        checked=checked,
        last_seq=last_good or None,
        broken_at_seq=seq,
        reason=reason,
    )


def _entry(e: dict[str, Any]) -> AuditLogEntry:
    return AuditLogEntry(
        log_id=e["log_id"],
        seq=e["seq"],
        user_id=e.get("user_id"),
        username=e.get("username"),
        activity_type=e.get("activity_type") or "other",
        action=e["action"],
        file_id=e.get("file_id"),
        description=e.get("description") or "",
        status=e.get("status", "success"),
        ip_address=e.get("ip_address"),
        created_at=e["created_at"],
        imported=bool(e.get("imported")),
        hash=e["hash"],
    )
