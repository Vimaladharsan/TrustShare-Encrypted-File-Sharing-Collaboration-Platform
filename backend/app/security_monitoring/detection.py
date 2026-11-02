"""Detection rules, checked automatically after every recorded activity.

How a rule works (sliding window in Redis):
  1. The activity matches the rule (e.g. a failed sign-in) → it is added to a sorted set
     `detect:<rule>:<subject>` scored by time; entries older than the window are dropped.
  2. If the set now holds MORE than the rule's limit → suspicious.
  3. One alert per rule and subject per window (a cooldown key), so an attack produces one clear
     alert instead of hundreds. The alert is a security event (severity, status "open"), and the
     event hooks notify the administrators.

Subjects: the account for failed sign-ins, the user (or the IP for anonymous visitors) for
denied access and downloads, the IP for link abuse. Thresholds come from .env (Settings.detect_*).
"""

import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from fastapi import Request

from app.core.config import Settings, get_settings
from app.db.redis import get_redis
from app.models import User
from app.services.security_events import EVENT_TYPES, record_security_event


@dataclass(frozen=True)
class Rule:
    name: str  # also the security event type
    activity: str  # what is counted, in words (shown to admins)
    applies: Callable[[dict[str, Any]], bool]
    subject: Callable[[dict[str, Any]], str | None]
    setting: str  # Settings prefix: detect_<setting>_limit / _minutes
    subject_kind: str

    def limit(self, settings: Settings) -> int:
        return getattr(settings, f"detect_{self.setting}_limit")

    def minutes(self, settings: Settings) -> int:
        return getattr(settings, f"detect_{self.setting}_minutes")


def _reason(activity: dict[str, Any]) -> str | None:
    return (activity.get("details") or {}).get("reason")


def _account(activity: dict[str, Any]) -> str | None:
    email = activity.get("actor_email") or (activity.get("details") or {}).get("email")
    return activity.get("user_id") or (email.lower() if email else None)


def _user_or_ip(activity: dict[str, Any]) -> str | None:
    return activity.get("user_id") or activity.get("ip_address")


RULES: list[Rule] = [
    Rule(
        name="repeated_failed_logins",
        activity="failed sign-ins (wrong password or code, or tries while locked)",
        applies=lambda a: a["action"] in ("auth.login.failed", "auth.login.locked"),
        subject=_account,
        setting="failed_logins",
        subject_kind="account",
    ),
    Rule(
        name="repeated_unauthorized_access",
        activity="denied accesses (someone else's file, missing permission, wrong vault password)",
        applies=lambda a: (
            a["action"] in ("file.access_denied", "auth.access_denied", "vault.unlock_failed")
        ),
        subject=_user_or_ip,
        setting="unauthorized",
        subject_kind="user or IP",
    ),
    Rule(
        name="excessive_downloads",
        activity="file downloads",
        applies=lambda a: a["action"] in ("file.download", "vault.file_downloaded"),
        subject=_user_or_ip,
        setting="downloads",
        subject_kind="user or IP",
    ),
    Rule(
        name="expired_link_abuse",
        activity="attempts to open expired share links",
        applies=lambda a: a["action"] == "share.access_denied" and _reason(a) == "SHARE_EXPIRED",
        subject=lambda a: a.get("ip_address"),
        setting="expired_link",
        subject_kind="IP",
    ),
    Rule(
        name="revoked_link_abuse",
        activity="attempts to open revoked share links",
        applies=lambda a: a["action"] == "share.access_denied" and _reason(a) == "SHARE_REVOKED",
        subject=lambda a: a.get("ip_address"),
        setting="revoked_link",
        subject_kind="IP",
    ),
]


def describe_rules() -> list[dict[str, Any]]:
    settings = get_settings()
    return [
        {
            "name": rule.name,
            "title": EVENT_TYPES[rule.name][1],
            "severity": EVENT_TYPES[rule.name][0],
            "counts": rule.activity,
            "per": rule.subject_kind,
            "limit": rule.limit(settings),
            "window_minutes": rule.minutes(settings),
            "condition": f"more than {rule.limit(settings)} within {rule.minutes(settings)} min",
        }
        for rule in RULES
    ]


async def evaluate(activity: dict[str, Any], user: User | None, request: Request | None) -> None:
    """Activity hook (registered in app/main.py): check every rule against this activity."""
    settings = get_settings()
    redis = get_redis()
    now = time.time()
    for rule in RULES:
        if not rule.applies(activity):
            continue
        subject = rule.subject(activity)
        if not subject:
            continue
        window = rule.minutes(settings) * 60
        key = f"detect:{rule.name}:{subject}"
        async with redis.pipeline(transaction=True) as pipe:
            pipe.zadd(key, {uuid.uuid4().hex: now})
            pipe.zremrangebyscore(key, 0, now - window)
            pipe.zcard(key)
            pipe.expire(key, window)
            _, _, count, _ = await pipe.execute()
        if count <= rule.limit(settings):
            continue
        # One alert per rule + subject per window.
        if not await redis.set(f"detect_cooldown:{rule.name}:{subject}", "1", nx=True, ex=window):
            continue
        await record_security_event(
            rule.name,
            request=request,
            user=user,
            email=activity.get("actor_email") or (activity.get("details") or {}).get("email"),
            details={
                "count": count,
                "window_minutes": window // 60,
                "last_action": activity["action"],
            },
            rule={
                "name": rule.name,
                "count": count,
                "limit": rule.limit(settings),
                "window_minutes": window // 60,
                "subject": subject,
            },
        )
