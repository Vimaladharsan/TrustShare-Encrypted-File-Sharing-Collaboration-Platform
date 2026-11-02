"""Creating, delivering and reading notifications.

notify(): store the notification → publish it on the user's Redis channel (their open browser
tabs get it instantly through the live stream) → send an email too if the type allows it and the
user hasn't turned it off. Real SMTP runs in a background thread so no request waits for it; the
email result is written back to the notification (sent / failed).
"""

import asyncio
import json
import logging
from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
from pymongo.asynchronous.database import AsyncDatabase
from redis.asyncio import Redis
from sqlalchemy import select

from app.core.errors import AppError
from app.core.permissions import Perm
from app.db.postgres import get_sessionmaker
from app.models import Permission, Role, User
from app.notifications.models import COLLECTION, PREFERENCES, TYPES, channel
from app.notifications.schemas import (
    Delivery,
    Notification,
    NotificationPage,
    NotificationStats,
    PreferenceItem,
    Preferences,
    TypeStat,
)
from app.services.email_service import Email, EmailSender, get_email_sender

logger = logging.getLogger(__name__)
_background: set[asyncio.Task] = set()  # keep references so tasks aren't garbage-collected
_app: Any = None


def bind_app(app: Any) -> None:
    """Remember the FastAPI app, so background work uses the same email sender as requests
    (tests replace it with a fake one through dependency_overrides)."""
    global _app
    _app = app


def current_sender() -> EmailSender:
    if _app is not None:
        return _app.dependency_overrides.get(get_email_sender, get_email_sender)()
    return get_email_sender()


class NotificationService:
    def __init__(self, db: AsyncDatabase, redis: Redis | None = None) -> None:
        self.db = db
        self.items = db[COLLECTION]
        self.prefs = db[PREFERENCES]
        self.redis = redis

    # ---------- create & deliver ----------

    async def notify(
        self,
        recipient: User,
        type_: str,
        title: str,
        message: str,
        *,
        severity: str = "info",
        link: str | None = None,
        data: dict[str, Any] | None = None,
        email: Email | None = None,
    ) -> dict[str, Any]:
        wants_email = email is not None and await self.email_enabled(str(recipient.id), type_)
        doc = {
            "user_id": str(recipient.id),
            "type": type_,
            "title": title,
            "message": message,
            "severity": severity,
            "link": link,
            "data": data or {},
            "read": False,
            "read_at": None,
            "email_status": "pending" if wants_email else ("skipped" if email else "none"),
            "recipient_email": recipient.email,  # admins' delivery report shows only this
            "created_at": datetime.now(UTC),
        }
        await self.items.insert_one(doc)
        await self._publish(doc)
        if wants_email and email is not None:
            await self._send_email(doc["_id"], email)
        return doc

    async def _publish(self, doc: dict[str, Any]) -> None:
        if self.redis is None:
            return
        try:
            payload = _public(doc).model_dump(mode="json")
            await self.redis.publish(channel(doc["user_id"]), json.dumps(payload))
        except Exception:
            logger.exception("Could not publish notification %s", doc["_id"])

    async def _send_email(self, notification_id: ObjectId, email: Email) -> None:
        sender = current_sender()

        async def deliver() -> None:
            try:
                result = await asyncio.to_thread(sender.send, email)
                if isinstance(sender, EmailSender):
                    status = {True: "sent", False: "failed"}.get(result, "not_configured")
                else:
                    status = "sent"  # test sender
            except Exception:
                logger.exception("Notification email failed")
                status = "failed"
            await self.items.update_one(
                {"_id": notification_id}, {"$set": {"email_status": status}}
            )

        if isinstance(sender, EmailSender):  # real SMTP: don't make anyone wait for it
            task = asyncio.create_task(deliver())
            _background.add(task)
            task.add_done_callback(_background.discard)
        else:
            await deliver()

    # ---------- preferences ----------

    async def email_enabled(self, user_id: str, type_: str) -> bool:
        kind = TYPES[type_]
        if not kind.email_optional:
            return False
        stored = await self.prefs.find_one({"user_id": user_id}) or {}
        return bool(stored.get("email", {}).get(type_, kind.email_default))

    async def preferences(self, user: User) -> Preferences:
        stored = (await self.prefs.find_one({"user_id": str(user.id)}) or {}).get("email", {})
        admin = Perm.AUDIT_READ in user.permission_codes
        return Preferences(
            items=[
                PreferenceItem(
                    type=name,
                    label=kind.label,
                    email=bool(stored.get(name, kind.email_default)) and kind.email_optional,
                    email_optional=kind.email_optional,
                )
                for name, kind in TYPES.items()
                if name != "security_alert" or admin
            ]
        )

    async def update_preferences(self, user: User, email: dict[str, bool]) -> Preferences:
        unknown = [name for name in email if name not in TYPES]
        if unknown:
            raise AppError("UNKNOWN_TYPE", f"Unknown notification type: {unknown[0]}", 400)
        changes = {
            f"email.{name}": value for name, value in email.items() if TYPES[name].email_optional
        }
        if changes:
            await self.prefs.update_one({"user_id": str(user.id)}, {"$set": changes}, upsert=True)
        return await self.preferences(user)

    # ---------- reading ----------

    async def page(
        self, user: User, unread_only: bool, type_: str | None, limit: int, offset: int
    ) -> NotificationPage:
        match: dict[str, Any] = {"user_id": str(user.id)}
        if unread_only:
            match["read"] = False
        if type_:
            match["type"] = type_
        total = await self.items.count_documents(match)
        cursor = self.items.find(match).sort("created_at", -1).skip(offset).limit(limit)
        return NotificationPage(
            items=[_public(d) for d in await cursor.to_list(length=limit)],
            total=total,
            unread=await self.unread(user),
        )

    async def unread(self, user: User) -> int:
        return await self.items.count_documents({"user_id": str(user.id), "read": False})

    async def mark_read(self, user: User, notification_id: str) -> Notification:
        try:
            oid = ObjectId(notification_id)
        except (InvalidId, TypeError) as exc:
            raise _not_found() from exc
        doc = await self.items.find_one_and_update(
            {"_id": oid, "user_id": str(user.id)},
            {"$set": {"read": True, "read_at": datetime.now(UTC)}},
            return_document=True,
        )
        if doc is None:
            raise _not_found()
        return _public(doc)

    async def mark_all_read(self, user: User) -> int:
        result = await self.items.update_many(
            {"user_id": str(user.id), "read": False},
            {"$set": {"read": True, "read_at": datetime.now(UTC)}},
        )
        return result.modified_count

    # ---------- admin: notification management ----------

    async def stats(self) -> NotificationStats:
        rows = await (
            await self.items.aggregate(
                [
                    {
                        "$group": {
                            "_id": "$type",
                            "sent": {"$sum": 1},
                            "read": {"$sum": {"$cond": ["$read", 1, 0]}},
                            "emails_sent": {
                                "$sum": {"$cond": [{"$eq": ["$email_status", "sent"]}, 1, 0]}
                            },
                            "emails_failed": {
                                "$sum": {"$cond": [{"$eq": ["$email_status", "failed"]}, 1, 0]}
                            },
                        }
                    }
                ]
            )
        ).to_list(length=None)
        by_type = [
            TypeStat(
                type=r["_id"],
                sent=r["sent"],
                read=r["read"],
                emails_sent=r["emails_sent"],
                emails_failed=r["emails_failed"],
            )
            for r in sorted(rows, key=lambda r: -r["sent"])
        ]
        recent = await self.items.find({}).sort("created_at", -1).limit(25).to_list(25)
        return NotificationStats(
            total=sum(t.sent for t in by_type),
            unread=sum(t.sent - t.read for t in by_type),
            emails_sent=sum(t.emails_sent for t in by_type),
            emails_failed=sum(t.emails_failed for t in by_type),
            by_type=by_type,
            recent=[
                Delivery(
                    id=str(d["_id"]),
                    type=d["type"],
                    severity=d.get("severity", "info"),
                    recipient_email=d.get("recipient_email"),
                    read=d.get("read", False),
                    email_status=d.get("email_status", "none"),
                    created_at=d["created_at"],
                )
                for d in recent
            ],
        )


async def active_admins() -> list[User]:
    """Everyone whose role may read the audit log – they receive security alerts."""
    async with get_sessionmaker()() as session:
        result = await session.scalars(
            select(User)
            .join(Role, User.role_id == Role.id)
            .where(
                User.is_active.is_(True), Role.permissions.any(Permission.code == Perm.AUDIT_READ)
            )
        )
        return list(result.all())


async def load_user(user_id: str) -> User | None:
    import uuid

    try:
        uid = uuid.UUID(user_id)
    except (ValueError, TypeError):
        return None
    async with get_sessionmaker()() as session:
        return await session.get(User, uid)


def _not_found() -> AppError:
    return AppError("NOTIFICATION_NOT_FOUND", "Notification not found.", 404)


def _public(d: dict[str, Any]) -> Notification:
    return Notification(
        id=str(d["_id"]),
        type=d["type"],
        title=d["title"],
        message=d["message"],
        severity=d.get("severity", "info"),
        link=d.get("link"),
        data=d.get("data") or {},
        read=d.get("read", False),
        read_at=d.get("read_at"),
        created_at=d["created_at"],
    )
