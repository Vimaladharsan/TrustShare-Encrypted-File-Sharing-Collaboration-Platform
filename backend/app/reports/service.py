"""The five reports the brief asks for: uploads, downloads, sharing, user activity, security.

Sources: activity_logs + security_events (MongoDB), users + shares (PostgreSQL), file metadata
(MongoDB, for type/size/owner). File names are never included – admins get file IDs and types.
"""

import uuid
from collections import Counter
from typing import Any

from pymongo.asynchronous.database import AsyncDatabase
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.activity_monitoring.models import activity_type_of
from app.analytics.queries import (
    DOWNLOAD_ACTIONS,
    REJECTED_UPLOAD_ACTIONS,
    UPLOAD_ACTIONS,
    Filters,
    category_of_extension,
    empty_days,
    extension_from,
    file_meta,
    people,
)
from app.audit.models import describe
from app.core.errors import AppError
from app.models import Share, User
from app.reports.schemas import Report
from app.services.security_events import EVENT_TYPES
from app.services.share_service import share_status

ROW_LIMIT = 500
FAILED_DOWNLOAD_ACTIONS = ["share.access_denied", "file.access_denied"]
SECURITY_LINK_REASONS = {"SHARE_EXPIRED": "expired", "SHARE_REVOKED": "revoked"}


def _counts(counter: Counter, key: str, who: dict[str, dict] | None = None) -> list[dict]:
    rows = []
    for value, count in counter.most_common(20):
        row = {key: value, "count": count}
        if who is not None:
            row["email"] = who.get(value or "", {}).get("email") or (
                "anonymous (link visitors)" if not value else None
            )
        rows.append(row)
    return rows


class ReportsService:
    def __init__(self, session: AsyncSession, db: AsyncDatabase) -> None:
        self.session = session
        self.db = db
        self.logs = db["activity_logs"]
        self.events = db["security_events"]

    def _report(self, name: str, title: str, f: Filters, **parts: Any) -> Report:
        return Report(
            report=name,
            title=title,
            from_date=f.period.from_date,
            to_date=f.period.to_date,
            filters={
                "user_id": f.user_id,
                "file_type": f.file_type,
                "activity_type": f.activity_type,
                "file_id": f.file_id,
            },
            row_limit=ROW_LIMIT,
            **parts,
        )

    async def _entries(self, f: Filters, actions: list[str]) -> list[dict[str, Any]]:
        cursor = self.logs.find(f.activity_match(actions)).sort("created_at", -1)
        return await cursor.to_list(length=None)

    # ---------- uploads ----------

    async def uploads(self, f: Filters) -> Report:
        entries = await self._entries(f, UPLOAD_ACTIONS + REJECTED_UPLOAD_ACTIONS)
        rows, by_user, by_type, reasons = [], Counter(), Counter(), Counter()
        days = empty_days(f.period, "succeeded", "rejected")
        total_bytes = 0
        for e in entries:
            details = e.get("details") or {}
            extension = extension_from(details)
            category = category_of_extension(extension)
            if f.file_type and category != f.file_type:
                continue
            ok = e["action"] in UPLOAD_ACTIONS
            by_user[e.get("user_id")] += 1
            by_type[extension or "unknown"] += 1
            if ok:
                total_bytes += details.get("size_bytes") or 0
            else:
                reasons[details.get("reason") or "unknown"] += 1
            day = days.get(f.period.day_of(e["created_at"]))
            if day:
                day["succeeded" if ok else "rejected"] += 1
            rows.append(
                {
                    "time": e["created_at"],
                    "user_id": e.get("user_id"),
                    "file_id": e.get("file_id"),
                    "file_type": extension,
                    "category": category,
                    "size_bytes": details.get("size_bytes"),
                    "vault": e["action"].startswith("vault."),
                    "status": "uploaded" if ok else "rejected",
                    "reason": None if ok else details.get("reason"),
                }
            )
        who = await people(self.session, set(by_user))
        for row in rows:
            row["user_email"] = who.get(row["user_id"] or "", {}).get("email")
        succeeded = sum(1 for r in rows if r["status"] == "uploaded")
        return self._report(
            "uploads",
            "File upload report",
            f,
            summary={
                "total": len(rows),
                "uploaded": succeeded,
                "rejected": len(rows) - succeeded,
                "bytes_uploaded": total_bytes,
                "users": len([u for u in by_user if u]),
            },
            breakdowns={
                "by_user": _counts(by_user, "user_id", who),
                "by_type": _counts(by_type, "file_type"),
                "rejected_by_reason": _counts(reasons, "reason"),
                "by_day": list(days.values()),
            },
            columns=[
                "time",
                "user_email",
                "user_id",
                "file_id",
                "file_type",
                "category",
                "size_bytes",
                "vault",
                "status",
                "reason",
            ],  # fmt: skip
            rows=rows[:ROW_LIMIT],
        )

    # ---------- downloads ----------

    async def downloads(self, f: Filters) -> Report:
        ok_entries = await self._entries(f, DOWNLOAD_ACTIONS)
        failed_entries = await self._entries(f, FAILED_DOWNLOAD_ACTIONS)
        meta = await file_meta(
            self.db, {e.get("file_id") for e in ok_entries + failed_entries if e.get("file_id")}
        )
        rows, by_user, by_file, reasons = [], Counter(), Counter(), Counter()
        days = empty_days(f.period, "downloads", "failed")
        for e, ok in [(e, True) for e in ok_entries] + [(e, False) for e in failed_entries]:
            info = meta.get(e.get("file_id") or "", {})
            if f.file_type and info.get("category") != f.file_type:
                continue
            details = e.get("details") or {}
            day = days.get(f.period.day_of(e["created_at"]))
            if ok:
                by_user[e.get("user_id")] += 1
                by_file[e.get("file_id")] += 1
            else:
                reasons[details.get("reason") or "NOT_YOUR_FILE"] += 1
            if day:
                day["downloads" if ok else "failed"] += 1
            rows.append(
                {
                    "time": e["created_at"],
                    "user_id": e.get("user_id"),
                    "file_id": e.get("file_id"),
                    "file_type": info.get("extension"),
                    "owner_id": info.get("owner_id") or details.get("owner_id"),
                    "via": details.get("via") or ("owner" if ok else None),
                    "status": "downloaded" if ok else "failed",
                    "reason": None if ok else details.get("reason") or "NOT_YOUR_FILE",
                    "ip_address": e.get("ip_address"),
                }
            )
        rows.sort(key=lambda r: r["time"], reverse=True)
        who = await people(
            self.session, {r["user_id"] for r in rows} | {r["owner_id"] for r in rows}
        )
        for row in rows:
            row["user_email"] = who.get(row["user_id"] or "", {}).get("email") or (
                "link visitor" if row["status"] == "downloaded" else None
            )
            row["owner_email"] = who.get(row["owner_id"] or "", {}).get("email")
        top = [
            {
                "file_id": file_id,
                "file_type": meta.get(file_id, {}).get("extension"),
                "owner_email": who.get(meta.get(file_id, {}).get("owner_id") or "", {}).get(
                    "email"
                ),
                "count": count,
            }
            for file_id, count in by_file.most_common(10)
        ]
        return self._report(
            "downloads",
            "File download report",
            f,
            summary={
                "downloads": sum(by_user.values()),
                "unique_users": len([u for u in by_user if u]),
                "link_visitor_downloads": by_user.get(None, 0),
                "failed_attempts": sum(reasons.values()),
                "files_downloaded": len(by_file),
            },
            breakdowns={
                "by_user": _counts(by_user, "user_id", who),
                "most_downloaded": top,
                "failed_by_reason": _counts(reasons, "reason"),
                "by_day": list(days.values()),
            },
            columns=[
                "time",
                "user_email",
                "file_id",
                "file_type",
                "owner_email",
                "via",
                "status",
                "reason",
                "ip_address",
            ],  # fmt: skip
            rows=rows[:ROW_LIMIT],
        )

    # ---------- sharing ----------

    async def sharing(self, f: Filters) -> Report:
        query = select(Share).where(
            Share.created_at >= f.period.start, Share.created_at < f.period.end
        )
        if f.user_id:
            query = query.where(Share.owner_id == _uuid(f.user_id))
        if f.file_id:
            query = query.where(Share.file_id == f.file_id)
        shares = list((await self.session.scalars(query.order_by(Share.created_at.desc()))).all())
        meta = await file_meta(self.db, {s.file_id for s in shares})
        if f.file_type:
            shares = [s for s in shares if meta.get(s.file_id, {}).get("category") == f.file_type]
        who = await people(
            self.session,
            {str(s.owner_id) for s in shares}
            | {str(s.recipient_id) for s in shares if s.recipient_id},
        )
        statuses, owners, recipients = Counter(), Counter(), Counter()
        days = empty_days(f.period, "link", "direct")
        rows = []
        for s in shares:
            status = share_status(s)
            statuses[status] += 1
            owners[str(s.owner_id)] += 1
            if s.recipient_id:
                recipients[str(s.recipient_id)] += 1
            day = days.get(f.period.day_of(s.created_at))
            if day:
                day["link" if s.share_type == "link" else "direct"] += 1
            rows.append(
                {
                    "created": s.created_at,
                    "share_id": str(s.id),
                    "owner_email": who.get(str(s.owner_id), {}).get("email"),
                    "file_id": s.file_id,
                    "file_type": meta.get(s.file_id, {}).get("extension"),
                    "share_type": "link" if s.share_type == "link" else "direct",
                    "permission": s.permission,
                    "recipient_email": who.get(str(s.recipient_id), {}).get("email")
                    if s.recipient_id
                    else None,
                    "status": status,
                    "expires": s.expires_at,
                    "downloads": s.download_count,
                    "max_downloads": s.max_downloads,
                }
            )
        return self._report(
            "sharing",
            "File sharing report",
            f,
            summary={
                "shares": len(shares),
                "files_shared": len({s.file_id for s in shares}),
                "links": sum(1 for s in shares if s.share_type == "link"),
                "direct": sum(1 for s in shares if s.share_type == "user"),
                "active": statuses["active"],
                "expired": statuses["expired"],
                "revoked": statuses["revoked"],
                "used_up": statuses["used_up"],
            },
            breakdowns={
                "by_owner": _counts(owners, "user_id", who),
                "recipients": _counts(recipients, "user_id", who),
                "by_status": [{"status": k, "count": v} for k, v in statuses.items()],
                "by_day": list(days.values()),
            },
            columns=[
                "created",
                "share_id",
                "owner_email",
                "file_id",
                "file_type",
                "share_type",
                "permission",
                "recipient_email",
                "status",
                "expires",
                "downloads",
                "max_downloads",
            ],  # fmt: skip
            rows=rows[:ROW_LIMIT],
        )

    # ---------- one user's activity ----------

    async def user_activity(self, user_id: str, f: Filters) -> Report:
        user = await self.session.get(User, _uuid(user_id))
        if user is None:
            raise AppError("USER_NOT_FOUND", "User not found.", 404)
        f.user_id = str(user.id)
        match = {"user_id": f.user_id, "created_at": f.period.current()}
        if f.activity_type:
            match["activity_type"] = f.activity_type
        if f.file_id:
            match["file_id"] = f.file_id
        entries = await self.logs.find(match).sort("created_at", -1).to_list(length=None)
        types, statuses = Counter(), Counter()
        days = empty_days(f.period, "activities", "failures")
        rows = []
        for e in entries:
            kind = e.get("activity_type") or activity_type_of(e["action"])
            types[kind] += 1
            statuses[e.get("status", "success")] += 1
            day = days.get(f.period.day_of(e["created_at"]))
            if day:
                day["activities"] += 1
                if e.get("status") == "failure":
                    day["failures"] += 1
            rows.append(
                {
                    "time": e["created_at"],
                    "activity_type": kind,
                    "action": e["action"],
                    "description": describe(e["action"], e.get("details")),  # no file names
                    "file_id": e.get("file_id"),
                    "status": e.get("status", "success"),
                    "ip_address": e.get("ip_address"),
                }
            )
        return self._report(
            "user_activity",
            f"User activity report – {user.full_name} ({user.email})",
            f,
            summary={
                "activities": len(entries),
                "failures": statuses["failure"],
                "logins": types["login"],
                "uploads": types["upload"],
                "downloads": types["download"],
                "shares": types["share"],
            },
            breakdowns={
                "by_type": _counts(types, "activity_type"),
                "by_day": list(days.values()),
            },
            columns=[
                "time",
                "activity_type",
                "action",
                "description",
                "file_id",
                "status",
                "ip_address",
            ],  # fmt: skip
            rows=rows[:ROW_LIMIT],
        )

    # ---------- security ----------

    async def security(self, f: Filters) -> Report:
        when = {"created_at": f.period.current()}
        event_match: dict[str, Any] = dict(when)
        if f.user_id:
            event_match["user_id"] = f.user_id
        events = await self.events.find(event_match).sort("created_at", -1).to_list(length=None)
        failed_logins = await self.logs.find(
            f.activity_match(["auth.login.failed"]),
            {"created_at": 1, "details": 1, "ip_address": 1},
        ).to_list(length=None)
        link_attempts = await self.logs.find(
            f.activity_match(["share.access_denied"]), {"details": 1}
        ).to_list(length=None)
        days = empty_days(f.period, "failed_logins", "alerts")
        for e in failed_logins:
            day = days.get(f.period.day_of(e["created_at"]))
            if day:
                day["failed_logins"] += 1
        types, severities, statuses, sources = Counter(), Counter(), Counter(), Counter()
        rows = []
        for e in events:
            types[e["type"]] += 1
            severities[e["severity"]] += 1
            statuses[e.get("status") or "open"] += 1
            sources[e.get("ip_address") or "unknown"] += 1
            day = days.get(f.period.day_of(e["created_at"]))
            if day:
                day["alerts"] += 1
            rows.append(
                {
                    "time": e["created_at"],
                    "alert_id": e.get("alert_id") or str(e["_id"]),
                    "type": e["type"],
                    "title": EVENT_TYPES.get(e["type"], ("", e["type"]))[1],
                    "severity": e["severity"],
                    "status": e.get("status") or "open",
                    "user_email": e.get("actor_email"),
                    "ip_address": e.get("ip_address"),
                    "message": e.get("message"),
                }
            )
        link_reasons = Counter(
            SECURITY_LINK_REASONS.get((e.get("details") or {}).get("reason"), "other")
            for e in link_attempts
        )
        return self._report(
            "security",
            "Security report",
            f,
            summary={
                "failed_logins": len(failed_logins),
                "unauthorized_attempts": types["unauthorized_access"]
                + types["repeated_unauthorized_access"],
                "suspicious_downloads": types["excessive_downloads"] + types["download_anomaly"],
                "expired_link_attempts": link_reasons["expired"],
                "revoked_link_attempts": link_reasons["revoked"],
                "alerts": len(events),
                "high_alerts": severities["high"],
                "open_alerts": statuses["open"],
            },
            breakdowns={
                "by_type": [
                    {"type": t, "title": EVENT_TYPES.get(t, ("", t))[1], "count": n}
                    for t, n in types.most_common()
                ],
                "by_severity": [{"severity": s, "count": n} for s, n in severities.items()],
                "by_status": [{"status": s, "count": n} for s, n in statuses.items()],
                "top_sources": _counts(sources, "ip_address"),
                "by_day": list(days.values()),
            },
            columns=[
                "time",
                "alert_id",
                "type",
                "title",
                "severity",
                "status",
                "user_email",
                "ip_address",
                "message",
            ],  # fmt: skip
            rows=rows[:ROW_LIMIT],
        )


def _uuid(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except (ValueError, TypeError) as exc:
        raise AppError("USER_NOT_FOUND", "User not found.", 404) from exc
