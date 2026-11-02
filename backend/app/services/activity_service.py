"""Append-only activity / audit log in MongoDB (collection "activity_logs").

Every important action – including failed ones – is recorded with who, what, when and from where.
The API offers no way to edit or delete these records.

Since Milestone 3 this class is a thin wrapper: `log()` hands everything to
`app.activity_monitoring.service.record_activity`, which also writes the hash-chained audit log
and runs suspicious-activity detection and notifications. Existing callers didn't need changes.
"""

from typing import Any

from fastapi import Request
from pymongo.asynchronous.database import AsyncDatabase

from app.activity_monitoring.models import COLLECTION
from app.models import User


class ActivityService:
    def __init__(self, db: AsyncDatabase) -> None:
        self.db = db
        self.logs = db[COLLECTION]

    async def log(
        self,
        request: Request,
        user: User | None,
        action: str,
        *,
        resource_type: str | None = None,
        resource_id: str | None = None,
        file_id: str | None = None,
        status: str = "success",
        details: dict[str, Any] | None = None,
    ) -> None:
        from app.activity_monitoring.service import record_activity

        await record_activity(
            request,
            user,
            action,
            resource_type=resource_type,
            resource_id=resource_id,
            file_id=file_id,
            status=status,
            details=details,
            db=self.db,
        )
