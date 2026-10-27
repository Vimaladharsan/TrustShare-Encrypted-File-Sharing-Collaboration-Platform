"""Security events for the admin Security Dashboard (MongoDB collection "security_events").

Activity logs record *everything a user does*; security events record only what a security team
should look at – each with a type and a severity (high / medium / low / info):

  multiple_failed_logins   3+ wrong passwords or codes in a row for one account     medium
  account_locked           the account was locked after too many failures           high
  suspicious_ip            many failed sign-ins from one IP (often across accounts) high
  new_ip_login             successful sign-in from an IP never seen for the account medium
  token_reuse              an old refresh token came back – possible token theft     high
  unauthorized_access      403 (missing permission), forged token, invalid link     medium/low
  blocked_request          rate limit hit, or a sign-in attempt on a locked account medium
  policy_violation         upload of a disallowed file type                         low
  file_threat              fake file type (content ≠ extension) or tampered file    high
  download_anomaly         unusually many downloads through one share link          medium
  admin_action             an admin changed, unlocked or deleted an account         info
  vault_locked             the secure vault locked after repeated wrong passwords   high

Recording must never break the user's request, so every failure here is only logged.
No secrets (passwords, tokens, keys) are ever put into an event.
"""

import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import Request

from app.core.logging import request_id_ctx
from app.core.rate_limit import client_ip
from app.db.mongo import get_mongo
from app.models import User

logger = logging.getLogger(__name__)

EVENT_TYPES: dict[str, tuple[str, str]] = {
    # type: (default severity, description shown on the dashboard)
    "multiple_failed_logins": ("medium", "Multiple failed sign-in attempts"),
    "account_locked": ("high", "Account locked after repeated failures"),
    "suspicious_ip": ("high", "Many failed sign-ins from one IP address"),
    "new_ip_login": ("medium", "Sign-in from a new IP address"),
    "token_reuse": ("high", "Refresh token reused – all sessions ended"),
    "unauthorized_access": ("medium", "Unauthorized access attempt"),
    "blocked_request": ("medium", "Request blocked"),
    "policy_violation": ("low", "Disallowed file type rejected"),
    "file_threat": ("high", "Potential file threat"),
    "download_anomaly": ("medium", "Unusually many downloads"),
    "admin_action": ("info", "Admin action"),
    "vault_locked": ("high", "Vault locked after wrong passwords"),
}
SEVERITIES = ("high", "medium", "low", "info")


async def record_security_event(
    event_type: str,
    *,
    request: Request | None = None,
    user: User | None = None,
    email: str | None = None,
    ip: str | None = None,
    severity: str | None = None,
    message: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    default_severity, title = EVENT_TYPES[event_type]
    event = {
        "type": event_type,
        "severity": severity or default_severity,
        "message": message or title,
        "user_id": str(user.id) if user else None,
        "actor_email": user.email if user else email,
        "ip_address": ip or (client_ip(request) if request else None),
        "details": details or {},
        "request_id": request_id_ctx.get(),
        "created_at": datetime.now(UTC),
    }
    try:
        await get_mongo()["security_events"].insert_one(event)
    except Exception:
        logger.exception("Could not record security event %s", event_type)
