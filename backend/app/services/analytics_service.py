"""Read-only reports for one user: Storage, Recent, File Analytics and their own Activity Log.

Everything is computed from real data – file metadata (MongoDB `files`) and the audit trail
(`activity_logs`). Days are counted in the user's time zone, and every metric is compared with the
period of the same length just before the selected one ("vs last period").
A user only ever sees their own files and the activity on them (privacy – admins included).
"""

from collections import defaultdict
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pymongo.asynchronous.database import AsyncDatabase

from app.core.errors import AppError
from app.models import User
from app.repositories.file_repository import to_object_id
from app.schemas.analytics import (
    ActivityEntry,
    ActivityPage,
    AnalyticsSummary,
    CategoryUsage,
    DownloadDay,
    FileAnalytics,
    Metric,
    RecentDownload,
    RecentFile,
    ShareDay,
    StorageReport,
    UploadDay,
)
from app.schemas.file import FileInfo
from app.services.file_validation import ALLOWED_TYPES, extension_of

MAX_RANGE_DAYS = 366
CATEGORIES = ("document", "spreadsheet", "presentation", "image", "text")
# Activity that makes a file "recent" for its owner.
RECENT_ACTIONS = ["file.upload", "file.preview", "file.download", "file.rename", "file.move"]
ACTIVITY_GROUPS = {
    "auth": {"$regex": r"^auth\."},
    "files": {"$regex": r"^(file|folder)\."},
    "sharing": {"$regex": r"^share\."},
}


def category_of(file_name: str) -> str:
    file_type = ALLOWED_TYPES.get(extension_of(file_name or ""))
    return file_type.category if file_type else "text"


class Period:
    """A date range in the user's time zone, plus the equally long period before it."""

    def __init__(self, from_date: date | None, to_date: date | None, timezone: str) -> None:
        try:
            self.tz = ZoneInfo(timezone)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise AppError("INVALID_TIMEZONE", "Unknown time zone.", 400) from exc
        self.timezone = timezone
        self.to_date = to_date or datetime.now(self.tz).date()
        self.from_date = from_date or self.to_date - timedelta(days=29)
        days = (self.to_date - self.from_date).days + 1
        if days < 1:
            raise AppError("INVALID_RANGE", "The start date must be before the end date.", 400)
        if days > MAX_RANGE_DAYS:
            raise AppError("INVALID_RANGE", f"Choose at most {MAX_RANGE_DAYS} days.", 400)
        self.days = [self.from_date + timedelta(days=i) for i in range(days)]
        self.start = datetime.combine(self.from_date, time.min, self.tz).astimezone(UTC)
        self.end = datetime.combine(self.to_date + timedelta(days=1), time.min, self.tz).astimezone(
            UTC
        )
        self.previous_start = self.start - (self.end - self.start)

    def current(self) -> dict[str, datetime]:
        return {"$gte": self.start, "$lt": self.end}

    def previous(self) -> dict[str, datetime]:
        return {"$gte": self.previous_start, "$lt": self.start}

    def day_of(self, moment: datetime) -> date:
        return moment.astimezone(self.tz).date()


class AnalyticsService:
    def __init__(self, db: AsyncDatabase) -> None:
        self.files = db["files"]
        self.logs = db["activity_logs"]

    # ---------- Storage page ----------

    async def storage(self, user: User) -> StorageReport:
        owner = str(user.id)
        by_category = await self._by_category(owner)
        trash = await self._sum({"owner_id": owner, "status": "trashed"})
        largest = (
            await self.files.find({"owner_id": owner, "status": "active"})
            .sort("size_bytes", -1)
            .limit(10)
            .to_list(length=10)
        )
        return StorageReport(
            used_bytes=sum(c.bytes for c in by_category),
            quota_bytes=user.storage_quota_bytes,
            trash_bytes=trash,
            by_category=by_category,
            largest=[FileInfo.from_doc(doc) for doc in largest],
        )

    async def _by_category(self, owner: str) -> list[CategoryUsage]:
        """Everything the user stores (trash included – it still counts toward the quota)."""
        cursor = await self.files.aggregate(
            [
                {"$match": {"owner_id": owner}},
                {
                    "$group": {
                        "_id": "$category",
                        "bytes": {"$sum": "$size_bytes"},
                        "files": {"$sum": 1},
                    }
                },
            ]
        )
        found = {row["_id"]: row for row in await cursor.to_list(length=None)}
        return [
            CategoryUsage(
                category=category,
                bytes=found.get(category, {}).get("bytes", 0),
                files=found.get(category, {}).get("files", 0),
            )
            for category in CATEGORIES
        ]

    async def _sum(self, match: dict[str, Any]) -> int:
        cursor = await self.files.aggregate(
            [{"$match": match}, {"$group": {"_id": None, "bytes": {"$sum": "$size_bytes"}}}]
        )
        rows = await cursor.to_list(length=1)
        return rows[0]["bytes"] if rows else 0

    # ---------- Recent page ----------

    async def recent_files(self, user: User, limit: int = 50) -> list[RecentFile]:
        """My files I recently uploaded, opened, downloaded, renamed or moved (newest first)."""
        owner = str(user.id)
        cursor = await self.logs.aggregate(
            [
                {
                    "$match": {
                        "user_id": owner,
                        "action": {"$in": RECENT_ACTIONS},
                        "status": "success",
                    }
                },
                {"$sort": {"created_at": -1}},
                {
                    "$group": {
                        "_id": "$resource_id",
                        "action": {"$first": "$action"},
                        "at": {"$first": "$created_at"},
                    }
                },
                {"$sort": {"at": -1}},
                {"$limit": limit * 2},  # some may be deleted, trashed or someone else's file
            ]
        )
        latest = await cursor.to_list(length=None)
        ids = [oid for row in latest if (oid := to_object_id(row["_id"]))]
        docs = await self.files.find(
            {"_id": {"$in": ids}, "owner_id": owner, "status": "active"}
        ).to_list(length=None)
        by_id = {str(doc["_id"]): doc for doc in docs}
        return [
            RecentFile(
                file=FileInfo.from_doc(by_id[row["_id"]]),
                last_action=row["action"],
                last_activity_at=row["at"],
            )
            for row in latest
            if row["_id"] in by_id
        ][:limit]

    # ---------- File Analytics ----------

    async def file_analytics(self, user: User, period: Period) -> FileAnalytics:
        owner = str(user.id)
        uploads = {"user_id": owner, "action": "file.upload"}
        downloads = _downloads_of(owner)
        shares = {"user_id": owner, "action": "share.create"}

        by_category = await self._by_category(owner)
        summary = AnalyticsSummary(
            storage_used_bytes=sum(c.bytes for c in by_category),
            quota_bytes=user.storage_quota_bytes,
            uploads=await self._metric(uploads, period),
            downloads=await self._metric(downloads, period),
            shares=await self._metric(shares, period),
        )
        recent_uploads = (
            await self.files.find({"owner_id": owner, "status": "active"})
            .sort("created_at", -1)
            .limit(5)
            .to_list(length=5)
        )
        return FileAnalytics(
            from_date=period.from_date,
            to_date=period.to_date,
            timezone=period.timezone,
            summary=summary,
            storage_by_category=by_category,
            uploads_by_day=await self._uploads_by_day(uploads, period),
            downloads_by_day=await self._downloads_by_day(downloads, period),
            shares_by_day=await self._shares_by_day(shares, period),
            recent_uploads=[FileInfo.from_doc(doc) for doc in recent_uploads],
            recent_downloads=await self._recent_downloads(owner, downloads),
        )

    async def _metric(self, match: dict[str, Any], period: Period) -> Metric:
        return Metric(
            value=await self.logs.count_documents({**match, "created_at": period.current()}),
            previous=await self.logs.count_documents({**match, "created_at": period.previous()}),
        )

    async def _in_period(
        self, match: dict[str, Any], period: Period, fields: list[str]
    ) -> list[dict[str, Any]]:
        projection = dict.fromkeys(["created_at", *fields], 1)
        return await self.logs.find({**match, "created_at": period.current()}, projection).to_list(
            length=None
        )

    async def _uploads_by_day(self, match: dict[str, Any], period: Period) -> list[UploadDay]:
        days = {day: UploadDay(date=day) for day in period.days}
        for entry in await self._in_period(match, period, ["details.file_name"]):
            day = days.get(period.day_of(entry["created_at"]))
            if day:
                category = category_of(entry.get("details", {}).get("file_name", ""))
                setattr(day, category, getattr(day, category) + 1)
        return list(days.values())

    async def _downloads_by_day(self, match: dict[str, Any], period: Period) -> list[DownloadDay]:
        days = {day: DownloadDay(date=day) for day in period.days}
        people: dict[date, set[str]] = defaultdict(set)
        fields = ["user_id", "ip_address", "details.via"]
        for entry in await self._in_period(match, period, fields):
            key = period.day_of(entry["created_at"])
            day = days.get(key)
            if not day:
                continue
            day.total += 1
            if entry.get("details", {}).get("via") in ("link", "direct_share"):
                day.shared += 1
            # Link visitors have no account: count them by IP address.
            people[key].add(entry.get("user_id") or f"ip:{entry.get('ip_address')}")
        for key, who in people.items():
            days[key].unique_users = len(who)
        return list(days.values())

    async def _shares_by_day(self, match: dict[str, Any], period: Period) -> list[ShareDay]:
        days = {day: ShareDay(date=day) for day in period.days}
        for entry in await self._in_period(match, period, ["details.share_type"]):
            day = days.get(period.day_of(entry["created_at"]))
            if day:
                if entry.get("details", {}).get("share_type") == "link":
                    day.link += 1
                else:
                    day.direct += 1
        return list(days.values())

    async def _recent_downloads(self, owner: str, match: dict[str, Any]) -> list[RecentDownload]:
        entries = await self.logs.find(match).sort("created_at", -1).limit(5).to_list(length=5)
        ids = [oid for e in entries if (oid := to_object_id(e.get("resource_id")))]
        sizes = {
            str(doc["_id"]): doc["size_bytes"]
            for doc in await self.files.find({"_id": {"$in": ids}}, {"size_bytes": 1}).to_list(
                length=None
            )
        }
        result = []
        for entry in entries:
            details = entry.get("details", {})
            if entry.get("user_id") == owner:
                who = "You"
            else:
                who = entry.get("actor_email") or "Link visitor"
            result.append(
                RecentDownload(
                    file_id=entry.get("resource_id"),
                    file_name=details.get("file_name", "Unknown file"),
                    category=category_of(details.get("file_name", "")),
                    size_bytes=sizes.get(entry.get("resource_id")),
                    downloaded_by=who,
                    via=details.get("via", "owner"),
                    created_at=entry["created_at"],
                )
            )
        return result

    # ---------- My Activity Logs ----------

    async def my_activity(
        self, user: User, group: str | None, limit: int, offset: int
    ) -> ActivityPage:
        match: dict[str, Any] = {"user_id": str(user.id)}
        if group in ACTIVITY_GROUPS:
            match["action"] = ACTIVITY_GROUPS[group]
        total = await self.logs.count_documents(match)
        entries = (
            await self.logs.find(match)
            .sort("created_at", -1)
            .skip(offset)
            .limit(limit)
            .to_list(length=limit)
        )
        return ActivityPage(
            items=[
                ActivityEntry(
                    action=e["action"],
                    status=e.get("status", "success"),
                    resource_type=e.get("resource_type"),
                    resource_id=e.get("resource_id"),
                    ip_address=e.get("ip_address"),
                    user_agent=e.get("user_agent"),
                    details=e.get("details") or {},
                    created_at=e["created_at"],
                )
                for e in entries
            ],
            total=total,
        )


def _downloads_of(owner: str) -> dict[str, Any]:
    """Downloads of this user's files: by themselves, by share recipients and by link visitors.
    (Downloads logged before Milestone 2 have no owner_id – those were always the owner's own.)"""
    return {
        "action": "file.download",
        "status": "success",
        "$or": [
            {"details.owner_id": owner},
            {"user_id": owner, "details.owner_id": {"$exists": False}},
        ],
    }
