"""Storage analytics and usage monitoring (admin). Sizes come from the stored file metadata, so
the totals are the real storage used (vault files included – sizes only)."""

import uuid
from collections import Counter, defaultdict
from typing import Any

from pymongo.asynchronous.database import AsyncDatabase
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.queries import (
    DOWNLOAD_ACTIONS,
    REJECTED_UPLOAD_ACTIONS,
    UPLOAD_ACTIONS,
    Filters,
    category_keys,
    category_of_extension,
    extension_from,
    file_meta,
    people,
)
from app.analytics.schemas import (
    CategoryStorage,
    DownloadDay,
    DownloadStatistics,
    FileStatistics,
    LocationStorage,
    ShareDay,
    SharingStatistics,
    StorageAnalytics,
    TopFile,
    UploadDay,
    UserCount,
    UserStorage,
    UserStorageList,
)
from app.models import Share, User
from app.services.share_service import share_status


class AnalyticsService:
    def __init__(self, session: AsyncSession, db: AsyncDatabase) -> None:
        self.session = session
        self.db = db
        self.files = db["files"]
        self.vault = db["vault_files"]
        self.logs = db["activity_logs"]

    # ---------- storage ----------

    def _file_match(self, filters: Filters) -> dict[str, Any]:
        match: dict[str, Any] = {}
        if filters.user_id:
            match["owner_id"] = filters.user_id
        if filters.file_type:
            match["category"] = filters.file_type
        return match

    async def storage(self, filters: Filters) -> StorageAnalytics:
        match = self._file_match(filters)
        rows = await self._group(
            self.files,
            match,
            {
                "category": "$category",
                "status": "$status",
                "location": "$storage_backend",
            },  # fmt: skip
        )
        vault_rows = await self._group(self.vault, match, {"category": "$category"})
        by_category: dict[str, CategoryStorage] = {
            c: CategoryStorage(category=c, files=0, bytes=0) for c in category_keys()
        }
        by_location: dict[str, LocationStorage] = {}
        active = trash = 0
        for row in rows:
            key = row["_id"]
            category = by_category.setdefault(
                key.get("category") or "other",
                CategoryStorage(category=key.get("category") or "other", files=0, bytes=0),
            )
            category.files += row["n"]
            category.bytes += row["bytes"]
            location = key.get("location") or "local"
            loc = by_location.setdefault(
                location, LocationStorage(location=location, files=0, bytes=0)
            )
            loc.files += row["n"]
            loc.bytes += row["bytes"]
            if key.get("status") == "trashed":
                trash += row["bytes"]
            else:
                active += row["bytes"]
        vault_bytes = sum(r["bytes"] for r in vault_rows)
        vault_files = sum(r["n"] for r in vault_rows)
        for row in vault_rows:
            by_category[row["_id"].get("category") or "other"].bytes += row["bytes"]
            by_category[row["_id"].get("category") or "other"].files += row["n"]
        owners = set(await self.files.distinct("owner_id", match)) | set(
            await self.vault.distinct("owner_id", match)
        )
        quota_query = select(func.coalesce(func.sum(User.storage_quota_bytes), 0)).where(
            User.is_active.is_(True)
        )
        return StorageAnalytics(
            total_bytes=active + trash + vault_bytes,
            total_files=sum(r["n"] for r in rows) + vault_files,
            active_bytes=active,
            trash_bytes=trash,
            vault_bytes=vault_bytes,
            vault_files=vault_files,
            users_with_files=len(owners),
            quota_total_bytes=int(await self.session.scalar(quota_query) or 0),
            by_category=list(by_category.values()),
            by_location=sorted(by_location.values(), key=lambda loc: -loc.bytes),
        )

    async def users_storage(self, filters: Filters) -> UserStorageList:
        match = self._file_match(filters)
        per_user: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"files": 0, "bytes": 0, "vault_files": 0, "vault_bytes": 0, "last": None}
        )
        for row in await self._group(self.files, match, {"owner": "$owner_id"}, last=True):
            item = per_user[row["_id"]["owner"]]
            item.update(files=row["n"], bytes=row["bytes"], last=row["last"])
        for row in await self._group(self.vault, match, {"owner": "$owner_id"}, last=True):
            item = per_user[row["_id"]["owner"]]
            item.update(vault_files=row["n"], vault_bytes=row["bytes"])
            if row["last"] and (item["last"] is None or row["last"] > item["last"]):
                item["last"] = row["last"]
        who = await people(self.session, set(per_user))
        items = []
        for user_id, item in per_user.items():
            person = who.get(user_id, {})
            used = item["bytes"] + item["vault_bytes"]
            quota = person.get("quota_bytes")
            items.append(
                UserStorage(
                    user_id=user_id,
                    email=person.get("email"),
                    full_name=person.get("full_name"),
                    role=person.get("role"),
                    files=item["files"],
                    bytes=item["bytes"],
                    vault_files=item["vault_files"],
                    vault_bytes=item["vault_bytes"],
                    quota_bytes=quota,
                    percent_used=round(100 * used / quota, 1) if quota else 0.0,
                    last_upload_at=item["last"],
                )
            )
        items.sort(key=lambda u: -(u.bytes + u.vault_bytes))
        return UserStorageList(total_bytes=sum(u.bytes + u.vault_bytes for u in items), items=items)

    # ---------- files, downloads, sharing ----------

    async def files_statistics(self, filters: Filters) -> FileStatistics:
        period = filters.period
        days = {day: UploadDay(date=day) for day in period.days}
        uploaded = 0
        async for entry in self.logs.find(filters.activity_match(UPLOAD_ACTIONS)):
            category = category_of_extension(extension_from(entry.get("details") or {}))
            if filters.file_type and category != filters.file_type:
                continue
            uploaded += 1
            day = days.get(period.day_of(entry["created_at"]))
            if day:
                setattr(day, category, getattr(day, category) + 1)
        downloads = await self._downloads(filters)
        storage = await self.storage(filters)
        shared = await self.session.scalars(
            select(Share.file_id).where(
                Share.created_at >= period.start, Share.created_at < period.end
            )
        )
        return FileStatistics(
            from_date=period.from_date,
            to_date=period.to_date,
            uploaded=uploaded,
            rejected_uploads=await self.logs.count_documents(
                filters.activity_match(REJECTED_UPLOAD_ACTIONS)
            ),
            downloaded=len(downloads),
            shared_files=len(set(shared.all())),
            total_files=storage.total_files,
            total_bytes=storage.total_bytes,
            uploads_by_day=list(days.values()),
            most_downloaded=await self._top_files(downloads),
        )

    async def downloads_statistics(self, filters: Filters) -> DownloadStatistics:
        period = filters.period
        downloads = await self._downloads(filters)
        days = {day: DownloadDay(date=day) for day in period.days}
        via = Counter()
        users = Counter()
        for entry in downloads:
            channel = (entry.get("details") or {}).get("via") or "owner"
            channel = channel if channel in ("owner", "direct_share", "link") else "owner"
            via[channel] += 1
            users[entry.get("user_id")] += 1
            day = days.get(period.day_of(entry["created_at"]))
            if day:
                setattr(day, channel, getattr(day, channel) + 1)
        who = await people(self.session, set(users))
        failed = {
            **filters.activity_match(["share.access_denied", "file.access_denied"]),
        }
        return DownloadStatistics(
            from_date=period.from_date,
            to_date=period.to_date,
            total=len(downloads),
            unique_users=len([u for u in users if u]),
            by_owner=via["owner"],
            via_direct_share=via["direct_share"],
            via_link=via["link"],
            failed_attempts=await self.logs.count_documents(failed),
            by_day=list(days.values()),
            most_downloaded=await self._top_files(downloads),
            by_user=[
                UserCount(user_id=uid, email=who.get(uid or "", {}).get("email"), count=n)
                for uid, n in users.most_common(10)
            ],
        )

    async def sharing_statistics(self, filters: Filters) -> SharingStatistics:
        period = filters.period
        query = select(Share).where(Share.created_at >= period.start, Share.created_at < period.end)
        if filters.user_id:
            try:
                query = query.where(Share.owner_id == uuid.UUID(filters.user_id))
            except ValueError:
                query = query.where(Share.owner_id.is_(None))  # not a user id: no results
        if filters.file_id:
            query = query.where(Share.file_id == filters.file_id)
        shares = list((await self.session.scalars(query)).all())
        if filters.file_type:
            meta = await file_meta(self.db, {s.file_id for s in shares})
            shares = [
                s for s in shares if meta.get(s.file_id, {}).get("category") == filters.file_type
            ]
        days = {day: ShareDay(date=day) for day in period.days}
        statuses = Counter(share_status(s) for s in shares)
        owners = Counter(str(s.owner_id) for s in shares)
        recipients = Counter(str(s.recipient_id) for s in shares if s.recipient_id)
        for share in shares:
            day = days.get(period.day_of(share.created_at))
            if day:
                if share.share_type == "link":
                    day.link += 1
                else:
                    day.direct += 1
        who = await people(self.session, set(owners) | set(recipients))
        return SharingStatistics(
            from_date=period.from_date,
            to_date=period.to_date,
            created=len(shares),
            link_shares=sum(1 for s in shares if s.share_type == "link"),
            direct_shares=sum(1 for s in shares if s.share_type == "user"),
            shared_files=len({s.file_id for s in shares}),
            active=statuses["active"],
            expired=statuses["expired"],
            revoked=statuses["revoked"],
            used_up=statuses["used_up"],
            by_day=list(days.values()),
            by_owner=[
                UserCount(user_id=uid, email=who.get(uid, {}).get("email"), count=n)
                for uid, n in owners.most_common(10)
            ],
            top_recipients=[
                UserCount(user_id=uid, email=who.get(uid, {}).get("email"), count=n)
                for uid, n in recipients.most_common(10)
            ],
        )

    # ---------- helpers ----------

    async def _downloads(self, filters: Filters) -> list[dict[str, Any]]:
        entries = await self.logs.find(filters.activity_match(DOWNLOAD_ACTIONS)).to_list(
            length=None
        )
        if not filters.file_type:
            return entries
        meta = await file_meta(self.db, {e.get("file_id") for e in entries if e.get("file_id")})
        return [
            e
            for e in entries
            if meta.get(e.get("file_id"), {}).get("category") == filters.file_type
        ]

    async def _top_files(self, downloads: list[dict[str, Any]], limit: int = 10) -> list[TopFile]:
        counts = Counter(e.get("file_id") for e in downloads if e.get("file_id"))
        top = counts.most_common(limit)
        meta = await file_meta(self.db, {file_id for file_id, _ in top})
        owners = await people(self.session, {m.get("owner_id") for m in meta.values()})
        return [
            TopFile(
                file_id=file_id,
                extension=meta.get(file_id, {}).get("extension"),
                category=meta.get(file_id, {}).get("category") or "other",
                owner_email=owners.get(meta.get(file_id, {}).get("owner_id") or "", {}).get(
                    "email"
                ),
                downloads=n,
            )
            for file_id, n in top
        ]

    @staticmethod
    async def _group(
        collection: Any, match: dict[str, Any], key: dict[str, str], last: bool = False
    ) -> list[dict[str, Any]]:
        group: dict[str, Any] = {"_id": key, "n": {"$sum": 1}, "bytes": {"$sum": "$size_bytes"}}
        if last:
            group["last"] = {"$max": "$created_at"}
        cursor = await collection.aggregate([{"$match": match}, {"$group": group}])
        return await cursor.to_list(length=None)
