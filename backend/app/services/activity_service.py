"""Append-only activity / audit log in MongoDB (collection "activity_logs").

Every important action – including failed ones – is recorded with who, what, when and from where.
The API offers no way to edit or delete these records.
"""

import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import Request
from pymongo.asynchronous.database import AsyncDatabase

from app.core.logging import request_id_ctx
from app.core.rate_limit import client_ip
from app.models import User

logger = logging.getLogger(__name__)


class ActivityService:
    def __init__(self, db: AsyncDatabase) -> None:
        self.logs = db["activity_logs"]

    async def log(
        self,
        request: Request,
        user: User | None,
        action: str,
        *,
        resource_type: str | None = None,
        resource_id: str | None = None,
        status: str = "success",
        details: dict[str, Any] | None = None,
    ) -> None:
        entry = {
            "user_id": str(user.id) if user else None,
            "actor_email": user.email if user else None,
            "action": action,  # e.g. "file.upload", "file.upload_rejected"
            "resource_type": resource_type,
            "resource_id": resource_id,
            "status": status,
            "ip_address": client_ip(request),
            "user_agent": request.headers.get("user-agent", "")[:200],
            "request_id": request_id_ctx.get(),
            "details": details or {},
            "created_at": datetime.now(UTC),
        }
        try:
            await self.logs.insert_one(entry)
        except Exception:
            # A logging failure must never break the user's action; record it in the app log.
            logger.exception("Could not write activity log for %s", action)
