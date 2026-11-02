"""The one place where activities are recorded – and the admin's view of them.

`record_activity()` is the reusable function the brief asks for. Every module calls it (through
`ActivityService.log`), and it:
  1. writes the activity record (activity_logs – the feed and the user's own history),
  2. appends a permanent, hash-chained entry to the audit log (app/audit),
  3. runs the registered hooks (suspicious-activity detection, notifications – later phases).
Recording must never break the user's request: every step only logs its own failures.
"""

import logging
import re
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from fastapi import Request
from pymongo.asynchronous.database import AsyncDatabase

from app.activity_monitoring.models import COLLECTION, activity_type_of, redact
from app.activity_monitoring.schemas import (
    ActivityFeed,
    ActivityRecord,
    ActivitySummary,
    ActivityTypeCount,
)
from app.core.logging import request_id_ctx
from app.core.rate_limit import client_ip
from app.db.mongo import get_mongo
from app.db.redis import get_redis
from app.models import User
from app.services.analytics_service import Period

logger = logging.getLogger(__name__)

ActivityHook = Callable[[dict[str, Any], User | None, Request | None], Awaitable[None]]
_hooks: list[ActivityHook] = []


def register_hook(hook: ActivityHook) -> None:
    """Run `hook(activity, user, request)` after every recorded activity."""
    if hook not in _hooks:
        _hooks.append(hook)


async def record_activity(
    request: Request | None,
    user: User | None,
    action: str,
    *,
    resource_type: str | None = None,
    resource_id: str | None = None,
    file_id: str | None = None,
    status: str = "success",
    details: dict[str, Any] | None = None,
    db: AsyncDatabase | None = None,
) -> dict[str, Any]:
    from app.audit.service import AuditService  # audit imports this module's models

    db = db if db is not None else get_mongo()
    entry: dict[str, Any] = {
        "user_id": str(user.id) if user else None,
        "actor_email": user.email if user else None,
        "action": action,  # e.g. "file.upload", "file.upload_rejected"
        "activity_type": activity_type_of(action),
        "resource_type": resource_type,
        "resource_id": resource_id,
        "file_id": file_id or (resource_id if resource_type == "file" else None),
        "status": status,
        "ip_address": client_ip(request) if request else None,  # None = background job
        "user_agent": request.headers.get("user-agent", "")[:200] if request else "system",
        "request_id": request_id_ctx.get(),
        "details": details or {},
        "created_at": datetime.now(UTC),
    }
    try:
        await db[COLLECTION].insert_one(entry)
    except Exception:
        logger.exception("Could not write activity log for %s", action)
    try:
        await AuditService(db).append(entry, user)
    except Exception:
        logger.exception("Could not write audit log for %s", action)
    await _publish(entry)
    for hook in list(_hooks):
        try:
            await hook(entry, user, request)
        except Exception:
            logger.exception(
                "Activity hook %s failed for %s", getattr(hook, "__name__", hook), action
            )
    return entry


FEED_CHANNEL = "activity_feed"


async def _publish(entry: dict[str, Any]) -> None:
    """Push the activity (names removed) to admins watching the live feed."""
    try:
        redis = get_redis()
    except RuntimeError:
        return  # scripts without Redis
    try:
        await redis.publish(FEED_CHANNEL, _record(entry).model_dump_json())
    except Exception:
        logger.exception("Could not publish activity %s", entry.get("action"))


class ActivityMonitoringService:
    """Read side for administrators (live feed + summary). Names are always redacted."""

    def __init__(self, db: AsyncDatabase) -> None:
        self.logs = db[COLLECTION]

    async def feed(
        self,
        *,
        user_id: str | None,
        activity_type: str | None,
        status: str | None,
        file_id: str | None,
        search: str | None,
        limit: int,
        offset: int,
    ) -> ActivityFeed:
        match: dict[str, Any] = {}
        if user_id:
            match["user_id"] = user_id
        if activity_type:
            match["activity_type"] = activity_type
        if status:
            match["status"] = status
        if file_id:
            match["file_id"] = file_id
        if search:
            pattern = {"$regex": re.escape(search), "$options": "i"}
            match["$or"] = [{"actor_email": pattern}, {"ip_address": pattern}, {"action": pattern}]
        total = await self.logs.count_documents(match)
        cursor = self.logs.find(match).sort("created_at", -1).skip(offset).limit(limit)
        return ActivityFeed(
            items=[_record(e) for e in await cursor.to_list(length=limit)], total=total
        )

    async def summary(self, period: Period) -> ActivitySummary:
        rows = await (
            await self.logs.aggregate(
                [
                    {"$match": {"created_at": period.current()}},
                    # Grouped by action, then mapped to a type here – so records from before
                    # Milestone 3 (no stored activity_type) are counted under the right type too.
                    {
                        "$group": {
                            "_id": {"action": "$action", "status": "$status"},
                            "n": {"$sum": 1},
                        }
                    },
                ]
            )
        ).to_list(length=None)
        counts: dict[str, ActivityTypeCount] = {}
        for row in rows:
            kind = activity_type_of(row["_id"].get("action") or "")
            item = counts.setdefault(kind, ActivityTypeCount(activity_type=kind))
            if row["_id"].get("status") == "failure":
                item.failure += row["n"]
            else:
                item.success += row["n"]
        users = await self.logs.distinct(
            "user_id", {"created_at": period.current(), "user_id": {"$ne": None}}
        )
        return ActivitySummary(
            from_date=period.from_date,
            to_date=period.to_date,
            total=sum(c.success + c.failure for c in counts.values()),
            failures=sum(c.failure for c in counts.values()),
            active_users=len(users),
            by_type=sorted(counts.values(), key=lambda c: -(c.success + c.failure)),
        )


def _record(e: dict[str, Any]) -> ActivityRecord:
    return ActivityRecord(
        id=str(e["_id"]) if isinstance(e["_id"], ObjectId) else e["_id"],
        user_id=e.get("user_id"),
        actor_email=e.get("actor_email"),
        action=e["action"],
        activity_type=e.get("activity_type") or activity_type_of(e["action"]),
        file_id=e.get("file_id")
        or (e.get("resource_id") if e.get("resource_type") == "file" else None),
        status=e.get("status", "success"),
        ip_address=e.get("ip_address"),
        details=redact(e.get("details")),
        created_at=e["created_at"],
    )
