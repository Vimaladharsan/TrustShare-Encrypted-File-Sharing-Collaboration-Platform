"""Read-only reports for admins: the Security Dashboard, the audit log and the system overview.

Routes allow this only with `audit:read` (security, audit) or `user:read` (system overview) –
checked by the backend, not just hidden in the menu. Admins see who did what and when, and how
much each account stores; they never get file contents (privacy rule, Milestone 2).
"""

import csv
import io
import ipaddress
import re
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from pymongo.asynchronous.database import AsyncDatabase
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.crypto.keyring import get_keyring
from app.models import Role, Share, User
from app.repositories.file_key_repository import FileKeyRepository
from app.schemas.admin_reports import (
    AccessDay,
    ActivityDay,
    AuditEntry,
    AuditPage,
    KeyStats,
    LoginDay,
    LoginEntry,
    LoginPage,
    SecurityEvent,
    SecurityEventPage,
    SecurityMetrics,
    SecurityOverview,
    ShareStats,
    SystemOverview,
    TypeCount,
    UserStats,
    UserStorage,
)
from app.schemas.analytics import Metric
from app.services.analytics_service import ACTIVITY_GROUPS, Period
from app.services.security_events import EVENT_TYPES, SEVERITIES

LOGIN_ACTIONS = {"auth.login.success": "success", "auth.login.failed": "failed"}
UNAUTHORIZED_TYPES = ["unauthorized_access", "blocked_request"]


AUDIT_EXPORT_LIMIT = 10_000
AUDIT_CSV_COLUMNS = [
    "time_utc",
    "action",
    "result",
    "actor_email",
    "user_id",
    "ip_address",
    "resource_type",
    "resource_id",
    "details",
    "user_agent",
]


def _csv_safe(value: str) -> str:
    """Stop spreadsheet formula injection: a cell starting with = + - @ (or tab/CR) would be run
    as a formula when the CSV is opened in Excel, so it is prefixed with an apostrophe."""
    return "'" + value if value[:1] in ("=", "+", "-", "@", "\t", "\r") else value


def _audit_entry(e: dict[str, Any]) -> AuditEntry:
    return AuditEntry(
        action=e["action"],
        status=e.get("status", "success"),
        resource_type=e.get("resource_type"),
        resource_id=e.get("resource_id"),
        ip_address=e.get("ip_address"),
        user_agent=e.get("user_agent"),
        details=e.get("details") or {},
        created_at=e["created_at"],
        actor_email=e.get("actor_email"),
        user_id=e.get("user_id"),
    )


def ip_location(ip: str | None) -> str:
    """Approximate location of an IP address. Private and local addresses are "Local network";
    public ones would need a GeoIP database (e.g. MaxMind GeoLite2) – not bundled, so "Unknown"."""
    try:
        address = ipaddress.ip_address(ip or "")
    except ValueError:
        return "Unknown"
    if address.is_private or address.is_loopback or address.is_link_local:
        return "Local network"
    return "Unknown (public IP)"


class AdminReportsService:
    def __init__(self, session: AsyncSession, db: AsyncDatabase) -> None:
        self.session = session
        self.logs = db["activity_logs"]
        self.events = db["security_events"]
        self.files = db["files"]

    # ---------- Security Dashboard ----------

    async def security_overview(self, period: Period) -> SecurityOverview:
        logins = {"action": {"$in": list(LOGIN_ACTIONS)}}
        unauthorized = {"type": {"$in": UNAUTHORIZED_TYPES}}
        metrics = SecurityMetrics(
            total_logins=await self._metric(self.logs, logins, period),
            successful_logins=await self._metric(
                self.logs, {"action": "auth.login.success"}, period
            ),
            failed_logins=await self._metric(self.logs, {"action": "auth.login.failed"}, period),
            unauthorized_attempts=await self._metric(self.events, unauthorized, period),
            security_events=await self._metric(self.events, {}, period),
        )

        login_days = {day: LoginDay(date=day) for day in period.days}
        for entry in await self.logs.find(
            {**logins, "created_at": period.current()}, {"action": 1, "created_at": 1}
        ).to_list(length=None):
            day = login_days.get(period.day_of(entry["created_at"]))
            if day:
                status = LOGIN_ACTIONS[entry["action"]]
                setattr(day, status, getattr(day, status) + 1)

        access_days = {day: AccessDay(date=day) for day in period.days}
        by_type: dict[str, int] = {}
        for event in await self.events.find(
            {"created_at": period.current()}, {"type": 1, "created_at": 1}
        ).to_list(length=None):
            by_type[event["type"]] = by_type.get(event["type"], 0) + 1
            day = access_days.get(period.day_of(event["created_at"]))
            if day and event["type"] == "unauthorized_access":
                day.unauthorized += 1
            elif day and event["type"] == "blocked_request":
                day.blocked += 1

        return SecurityOverview(
            from_date=period.from_date,
            to_date=period.to_date,
            metrics=metrics,
            logins_by_day=list(login_days.values()),
            access_by_day=list(access_days.values()),
            events_by_type=[
                TypeCount(type=t, label=EVENT_TYPES.get(t, ("", t))[1], count=c)
                for t, c in sorted(by_type.items(), key=lambda item: -item[1])
            ],
            recent_logins=(await self.logins(None, 8, 0)).items,
            recent_events=(await self.security_events(None, None, 8, 0)).items,
        )

    async def logins(self, status: str | None, limit: int, offset: int) -> LoginPage:
        actions = [a for a, s in LOGIN_ACTIONS.items() if status in (None, s)]
        match = {"action": {"$in": actions}}
        total = await self.logs.count_documents(match)
        entries = await self._page(self.logs, match, limit, offset)
        names = await self._names([e.get("user_id") for e in entries])
        return LoginPage(
            items=[
                LoginEntry(
                    user_name=names.get(e.get("user_id") or ""),
                    email=e.get("actor_email") or e.get("details", {}).get("email"),
                    ip_address=e.get("ip_address"),
                    location=ip_location(e.get("ip_address")),
                    status=LOGIN_ACTIONS[e["action"]],
                    method=e.get("details", {}).get("method"),
                    reason=e.get("details", {}).get("reason"),
                    created_at=e["created_at"],
                )
                for e in entries
            ],
            total=total,
        )

    async def security_events(
        self, severity: str | None, event_type: str | None, limit: int, offset: int
    ) -> SecurityEventPage:
        match: dict[str, Any] = {}
        if severity in SEVERITIES:
            match["severity"] = severity
        if event_type in EVENT_TYPES:
            match["type"] = event_type
        total = await self.events.count_documents(match)
        return SecurityEventPage(
            items=[
                SecurityEvent(
                    type=e["type"],
                    severity=e["severity"],
                    message=e.get("message", ""),
                    actor_email=e.get("actor_email"),
                    ip_address=e.get("ip_address"),
                    details=e.get("details") or {},
                    created_at=e["created_at"],
                )
                for e in await self._page(self.events, match, limit, offset)
            ],
            total=total,
        )

    # ---------- audit log ----------

    async def audit(
        self,
        search: str | None,
        group: str | None,
        status: str | None,
        limit: int,
        offset: int,
    ) -> AuditPage:
        match = self._audit_match(search, group, status)
        total = await self.logs.count_documents(match)
        return AuditPage(
            items=[_audit_entry(e) for e in await self._page(self.logs, match, limit, offset)],
            total=total,
        )

    async def audit_csv(
        self, search: str | None, group: str | None, status: str | None
    ) -> tuple[str, int]:
        """The audit log (same filters as the viewer) as CSV text, newest first, at most
        AUDIT_EXPORT_LIMIT rows. Returns (csv text, number of rows)."""
        match = self._audit_match(search, group, status)
        entries = await self._page(self.logs, match, AUDIT_EXPORT_LIMIT, 0)
        out = io.StringIO()
        writer = csv.writer(out)
        writer.writerow(AUDIT_CSV_COLUMNS)
        for e in entries:
            entry = _audit_entry(e)
            details = "; ".join(
                f"{k}={v}" for k, v in entry.details.items() if v is not None and v != ""
            )
            writer.writerow(
                [
                    _csv_safe(value)
                    for value in (
                        entry.created_at.astimezone(UTC).isoformat(timespec="seconds"),
                        entry.action,
                        entry.status,
                        entry.actor_email or "",
                        entry.user_id or "",
                        entry.ip_address or "",
                        entry.resource_type or "",
                        entry.resource_id or "",
                        details,
                        entry.user_agent or "",
                    )
                ]
            )
        return out.getvalue(), len(entries)

    @staticmethod
    def _audit_match(search: str | None, group: str | None, status: str | None) -> dict:
        match: dict[str, Any] = {}
        if search:
            pattern = {"$regex": re.escape(search), "$options": "i"}  # literal text, not a regex
            match["$or"] = [
                {"actor_email": pattern},
                {"details.email": pattern},
                {"action": pattern},
                {"ip_address": pattern},
            ]
        if group in ACTIVITY_GROUPS:
            match["action"] = ACTIVITY_GROUPS[group]
        elif group == "admin":
            match["action"] = {"$regex": r"^admin\."}
        if status in ("success", "failure"):
            match["status"] = status
        return match

    # ---------- Admin Dashboard ----------

    async def system_overview(self, period: Period) -> SystemOverview:
        settings = get_settings()
        cutoff = datetime.now(UTC) - timedelta(days=settings.inactive_account_days)
        last_seen = func.coalesce(User.last_login_at, User.created_at)
        row = (
            await self.session.execute(
                select(
                    func.count(),
                    func.count().filter(User.is_active.is_(True)),
                    func.count().filter(last_seen < cutoff),
                )
            )
        ).one()
        roles = dict(
            (
                await self.session.execute(
                    select(Role.name, func.count(User.id))
                    .join(User, User.role_id == Role.id, isouter=True)
                    .group_by(Role.name)
                )
            ).all()
        )

        cursor = await self.files.aggregate(
            [
                {
                    "$group": {
                        "_id": "$owner_id",
                        "files": {"$sum": 1},
                        "bytes": {"$sum": "$size_bytes"},
                    }
                },
                {"$sort": {"bytes": -1}},
            ]
        )
        per_owner = await cursor.to_list(length=None)
        top = per_owner[:20]
        people = await self._people([r["_id"] for r in top])

        now = datetime.now(UTC)
        ended = (
            (Share.revoked_at.is_not(None))
            | (Share.expires_at <= now)
            | (Share.max_downloads.is_not(None) & (Share.download_count >= Share.max_downloads))
        )
        share_row = (
            await self.session.execute(
                select(
                    func.count().filter((Share.share_type == "link") & ~ended),
                    func.count().filter((Share.share_type == "link") & ended),
                    func.count().filter((Share.share_type == "user") & ~ended),
                    func.count().filter((Share.share_type == "user") & ended),
                    func.coalesce(
                        func.sum(case((Share.share_type == "link", Share.download_count), else_=0)),
                        0,
                    ),
                )
            )
        ).one()

        days = {day: ActivityDay(date=day) for day in period.days}
        for entry in await self.logs.find(
            {"action": {"$in": ["file.upload", "file.download"]}, "created_at": period.current()},
            {"action": 1, "created_at": 1},
        ).to_list(length=None):
            day = days.get(period.day_of(entry["created_at"]))
            if day:
                if entry["action"] == "file.upload":
                    day.uploads += 1
                else:
                    day.downloads += 1

        week = {"created_at": {"$gte": now - timedelta(days=7)}}
        severity_counts = {
            s: await self.events.count_documents({**week, "severity": s}) for s in SEVERITIES
        }
        keyring = get_keyring()
        return SystemOverview(
            users=UserStats(
                total=row[0],
                active=row[1],
                disabled=row[0] - row[1],
                inactive_30_days=row[2],
                by_role=roles,
            ),
            total_files=sum(r["files"] for r in per_owner),
            total_bytes=sum(r["bytes"] for r in per_owner),
            storage_by_user=[
                UserStorage(
                    user_id=r["_id"],
                    email=people.get(r["_id"], (None, None, None))[0],
                    full_name=people.get(r["_id"], (None, None, None))[1],
                    files=r["files"],
                    bytes=r["bytes"],
                    quota_bytes=people.get(r["_id"], (None, None, None))[2],
                )
                for r in top
            ],
            shares=ShareStats(
                links_active=share_row[0],
                links_ended=share_row[1],
                direct_active=share_row[2],
                direct_ended=share_row[3],
                link_downloads=share_row[4],
            ),
            activity_by_day=list(days.values()),
            keys=KeyStats(
                active_version=keyring.active_version,
                configured_versions=keyring.versions,
                keys_by_version=await FileKeyRepository(self.session).count_by_version(),
            ),
            events_last_7_days=severity_counts,
            storage_provider=settings.storage_label,
        )

    # ---------- helpers ----------

    async def _metric(self, collection: Any, match: dict[str, Any], period: Period) -> Metric:
        return Metric(
            value=await collection.count_documents({**match, "created_at": period.current()}),
            previous=await collection.count_documents({**match, "created_at": period.previous()}),
        )

    @staticmethod
    async def _page(collection: Any, match: dict[str, Any], limit: int, offset: int) -> list:
        cursor = collection.find(match).sort("created_at", -1).skip(offset).limit(limit)
        return await cursor.to_list(length=limit)

    async def _names(self, user_ids: list[str | None]) -> dict[str, str]:
        return {uid: person[1] for uid, person in (await self._people(user_ids)).items()}

    async def _people(self, user_ids: list[str | None]) -> dict[str, tuple[str, str, int]]:
        ids = []
        for value in {u for u in user_ids if u}:
            try:
                ids.append(uuid.UUID(value))
            except ValueError:
                continue
        if not ids:
            return {}
        result = await self.session.execute(
            select(User.id, User.email, User.full_name, User.storage_quota_bytes).where(
                User.id.in_(ids)
            )
        )
        return {str(r[0]): (r[1], r[2], r[3]) for r in result.all()}
