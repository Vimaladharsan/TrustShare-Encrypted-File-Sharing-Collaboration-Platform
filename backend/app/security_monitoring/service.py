"""Security monitoring for administrators: summary, filtered alerts and the alert workflow.

Workflow: every security event starts "open"; an admin can acknowledge it (looking into it),
resolve it with a note, or reopen it. Each change is recorded in the activity/audit log.
Events created before Milestone 3 have no status – they count as "open".
"""

import contextlib
import re
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import Request
from pymongo import ReturnDocument
from pymongo.asynchronous.database import AsyncDatabase

from app.activity_monitoring.models import redact
from app.activity_monitoring.service import record_activity
from app.core.errors import AppError
from app.models import User
from app.security_monitoring.schemas import (
    AlertUpdate,
    MonitoringSummary,
    SecurityAlert,
    SecurityAlertPage,
    TypeCount,
)
from app.services.analytics_service import Period
from app.services.security_events import EVENT_TYPES, SEVERITIES

UNAUTHORIZED_TYPES = ["unauthorized_access", "repeated_unauthorized_access"]
DOWNLOAD_TYPES = ["excessive_downloads", "download_anomaly"]
OPEN = {"$or": [{"status": "open"}, {"status": {"$exists": False}}, {"status": None}]}
TRANSITIONS = {
    "acknowledge": ("acknowledged", "admin.alert_acknowledged"),
    "resolve": ("resolved", "admin.alert_resolved"),
    "reopen": ("open", "admin.alert_reopened"),
}


class SecurityMonitoringService:
    def __init__(self, db: AsyncDatabase) -> None:
        self.db = db
        self.events = db["security_events"]
        self.logs = db["activity_logs"]

    async def summary(self, period: Period) -> MonitoringSummary:
        when = {"created_at": period.current()}
        by_severity = {
            s: await self.events.count_documents({**when, "severity": s}) for s in SEVERITIES
        }
        by_type = await (
            await self.events.aggregate(
                [{"$match": when}, {"$group": {"_id": "$type", "n": {"$sum": 1}}}]
            )
        ).to_list(length=None)
        denied_link = {**when, "action": "share.access_denied"}
        recent = (
            await self.events.find({**OPEN, **when}).sort("created_at", -1).limit(10).to_list(10)
        )
        return MonitoringSummary(
            from_date=period.from_date,
            to_date=period.to_date,
            total_events=sum(by_severity.values()),
            open_alerts=await self.events.count_documents({**OPEN, **when}),
            by_severity=by_severity,
            failed_logins=await self.logs.count_documents({**when, "action": "auth.login.failed"}),
            unauthorized_attempts=await self.events.count_documents(
                {**when, "type": {"$in": UNAUTHORIZED_TYPES}}
            ),
            suspicious_downloads=await self.events.count_documents(
                {**when, "type": {"$in": DOWNLOAD_TYPES}}
            ),
            expired_link_attempts=await self.logs.count_documents(
                {**denied_link, "details.reason": "SHARE_EXPIRED"}
            ),
            revoked_link_attempts=await self.logs.count_documents(
                {**denied_link, "details.reason": "SHARE_REVOKED"}
            ),
            alerts_by_type=sorted(
                (
                    TypeCount(type=r["_id"], title=_title(r["_id"]), count=r["n"])
                    for r in by_type
                    if r["_id"]
                ),
                key=lambda t: -t.count,
            ),
            recent_alerts=[_alert(e) for e in recent],
        )

    async def alerts(
        self,
        *,
        user: str | None,
        event_type: str | None,
        severity: str | None,
        status: str | None,
        from_date: date | None,
        to_date: date | None,
        tz: str,
        limit: int,
        offset: int,
    ) -> SecurityAlertPage:
        conditions: list[dict[str, Any]] = []
        if user:  # a user id, or part of an email
            pattern = {"$regex": re.escape(user), "$options": "i"}
            conditions.append({"$or": [{"user_id": user}, {"actor_email": pattern}]})
        if event_type:
            conditions.append({"type": event_type})
        if severity:
            conditions.append({"severity": severity})
        if status == "open":
            conditions.append(OPEN)
        elif status:
            conditions.append({"status": status})
        if from_date or to_date:
            conditions.append({"created_at": _date_range(from_date, to_date, tz)})
        match = {"$and": conditions} if conditions else {}
        total = await self.events.count_documents(match)
        cursor = self.events.find(match).sort("created_at", -1).skip(offset).limit(limit)
        return SecurityAlertPage(
            items=[_alert(e) for e in await cursor.to_list(length=limit)], total=total
        )

    async def get(self, alert_id: str) -> SecurityAlert:
        return _alert(await self._find(alert_id))

    async def update(
        self, alert_id: str, change: AlertUpdate, admin: User, request: Request
    ) -> SecurityAlert:
        event = await self._find(alert_id)
        status, action = TRANSITIONS[change.action]
        now = datetime.now(UTC)
        fields: dict[str, Any] = {"status": status}
        if change.note is not None:
            fields["note"] = change.note.strip() or None
        if change.action == "acknowledge":
            fields.update(acknowledged_by=admin.email, acknowledged_at=now)
        elif change.action == "resolve":
            fields.update(resolved_by=admin.email, resolved_at=now)
        else:
            fields.update(resolved_by=None, resolved_at=None)
        updated = await self.events.find_one_and_update(
            {"_id": event["_id"]}, {"$set": fields}, return_document=ReturnDocument.AFTER
        )
        await record_activity(
            request,
            admin,
            action,
            resource_type="security_event",
            resource_id=str(event["_id"]),
            details={"alert_type": event["type"], "severity": event["severity"]},
            db=self.db,
        )
        return _alert(updated)

    async def _find(self, alert_id: str) -> dict[str, Any]:
        query: dict[str, Any] = {"alert_id": alert_id}
        with contextlib.suppress(InvalidId, TypeError):  # not an ObjectId: look up by alert_id
            query = {"$or": [{"_id": ObjectId(alert_id)}, {"alert_id": alert_id}]}
        event = await self.events.find_one(query)
        if event is None:
            raise AppError("ALERT_NOT_FOUND", "Security alert not found.", 404)
        return event


def _title(event_type: str) -> str:
    return EVENT_TYPES.get(event_type, ("", event_type.replace("_", " ").capitalize()))[1]


def _date_range(from_date: date | None, to_date: date | None, tz: str) -> dict[str, datetime]:
    try:
        zone = ZoneInfo(tz)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise AppError("INVALID_TIMEZONE", "Unknown time zone.", 400) from exc
    when: dict[str, datetime] = {}
    if from_date:
        when["$gte"] = datetime.combine(from_date, time.min, zone).astimezone(UTC)
    if to_date:
        when["$lt"] = datetime.combine(to_date + timedelta(days=1), time.min, zone).astimezone(UTC)
    return when


def _alert(e: dict[str, Any]) -> SecurityAlert:
    return SecurityAlert(
        id=str(e["_id"]),
        alert_id=e.get("alert_id"),
        type=e["type"],
        title=_title(e["type"]),
        severity=e["severity"],
        status=e.get("status") or "open",
        message=e.get("message", ""),
        user_id=e.get("user_id"),
        actor_email=e.get("actor_email"),
        ip_address=e.get("ip_address"),
        rule=e.get("rule"),
        details=redact(e.get("details")),
        created_at=e["created_at"],
        acknowledged_by=e.get("acknowledged_by"),
        acknowledged_at=e.get("acknowledged_at"),
        resolved_by=e.get("resolved_by"),
        resolved_at=e.get("resolved_at"),
        note=e.get("note"),
    )
