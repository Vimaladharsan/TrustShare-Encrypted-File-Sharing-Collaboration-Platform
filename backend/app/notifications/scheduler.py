"""Background job (every SCHEDULER_INTERVAL_SECONDS, started with the API):

  1. Share links / direct shares expiring within LINK_REMINDER_HOURS → remind the owner once
     (in-app + email), `shares.reminder_sent_at` set.
  2. Shares that have just expired → record a "share.expired" activity (so expiry appears in the
     activity and audit logs, as the brief asks) + tell the owner; `expiry_recorded_at` set.

A Redis lock makes sure only one copy runs, even with several API processes.
"""

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.activity_monitoring.service import record_activity
from app.core.config import get_settings
from app.db.mongo import get_mongo
from app.db.postgres import get_sessionmaker
from app.db.redis import get_redis
from app.models import Share, User
from app.notifications.service import NotificationService
from app.repositories.file_repository import FileRepository
from app.services.email_service import notification_email

logger = logging.getLogger(__name__)
LOCK = "scheduler:lock"
BATCH = 500


async def run_once(now: datetime | None = None) -> dict[str, int]:
    """One pass of the job. Returns how many reminders and expiries were handled."""
    now = now or datetime.now(UTC)
    settings = get_settings()
    soon = now + timedelta(hours=settings.link_reminder_hours)
    service = NotificationService(get_mongo(), get_redis())
    files = FileRepository(get_mongo())
    reminded = expired = 0
    async with get_sessionmaker()() as session:
        due = await session.scalars(
            select(Share)
            .where(
                Share.revoked_at.is_(None),
                Share.reminder_sent_at.is_(None),
                Share.expires_at.is_not(None),
                Share.expires_at > now,
                Share.expires_at <= soon,
            )
            .limit(BATCH)
        )
        for share in due.all():
            owner = await session.get(User, share.owner_id)
            if owner is not None and owner.is_active:
                await _remind(service, owner, share, await _name(files, share), now)
                reminded += 1
            share.reminder_sent_at = now
        gone = await session.scalars(
            select(Share)
            .where(
                Share.revoked_at.is_(None),
                Share.expiry_recorded_at.is_(None),
                Share.expires_at.is_not(None),
                Share.expires_at <= now,
            )
            .limit(BATCH)
        )
        for share in gone.all():
            owner = await session.get(User, share.owner_id)
            if owner is not None:
                await _record_expiry(service, owner, share, await _name(files, share))
                expired += 1
            share.expiry_recorded_at = now
        await session.commit()
    return {"reminders": reminded, "expired": expired}


async def _name(files: FileRepository, share: Share) -> str:
    doc = await files.get(share.file_id)
    return doc["original_name"] if doc else "a file"


async def _remind(
    service: NotificationService, owner: User, share: Share, name: str, now: datetime
) -> None:
    hours = max(1, round((share.expires_at - now).total_seconds() / 3600))
    kind = "share link" if share.share_type == "link" else "direct share"
    when = share.expires_at.astimezone(UTC).strftime("%d %b %Y, %H:%M UTC")
    message = f"Your {kind} for “{name}” expires in about {hours} hour(s) ({when})."
    link = f"{get_settings().frontend_url}/shared-by-me"
    await service.notify(
        owner,
        "link_expiring",
        "A share is about to expire",
        message,
        severity="warning",
        link="/shared-by-me",
        data={"share_id": str(share.id), "file_id": share.file_id, "expires_at": when},
        email=notification_email(
            owner.email,
            owner.full_name,
            "A share is about to expire",
            message + " Create a new one if it should keep working.",
            "Open Shared by me",
            link,
            "Expiry reminders can be turned off in Settings → Notifications.",
        ),
    )


async def _record_expiry(
    service: NotificationService, owner: User, share: Share, name: str
) -> None:
    await record_activity(
        None,
        owner,
        "share.expired",
        resource_type="file",
        resource_id=share.file_id,
        details={"share_id": str(share.id), "share_type": share.share_type, "file_name": name},
    )
    kind = "share link" if share.share_type == "link" else "direct share"
    await service.notify(
        owner,
        "link_expired",
        "A share has expired",
        f"Your {kind} for “{name}” has expired and no longer works.",
        link="/shared-by-me",
        data={"share_id": str(share.id), "file_id": share.file_id},
    )


async def loop() -> None:
    """Runs until the API stops."""
    settings = get_settings()
    while True:
        try:
            redis = get_redis()
            ttl = max(30, settings.scheduler_interval_seconds - 10)
            if await redis.set(LOCK, "1", nx=True, ex=ttl):
                result = await run_once()
                if any(result.values()):
                    logger.info("Scheduler: %s", result)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Scheduler run failed")
        await asyncio.sleep(settings.scheduler_interval_seconds)
