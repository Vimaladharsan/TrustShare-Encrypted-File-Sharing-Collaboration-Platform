"""When notifications are created – listening to activities and security events (no other module
needs to know about notifications):

  share.create (direct)            → recipient: "X shared “file” with you"          (+ email)
  share.update (direct)            → recipient: "X changed your access to “file”"
  share.create_batch (direct)      → recipient: "X shared 4 files with you"     (+ one email)
  file.download via link / share   → owner: "X downloaded “file”" (max 1 per file per 10 min)
  security event, rule-based or high severity → every admin: security alert   (+ email if high,
                                                max 1 email per type per 15 min)
  account events (new-IP sign-in, lockout, brute force, token reuse, vault lock) → that user
The background job (scheduler.py) adds link-expiry reminders and "link expired".
Admin alerts never contain file names (privacy rule); owners and recipients see their own.
"""

from datetime import UTC, datetime
from typing import Any

from fastapi import Request

from app.core.config import get_settings
from app.db.mongo import get_mongo
from app.db.redis import get_redis
from app.models import User
from app.notifications.service import NotificationService, active_admins, load_user
from app.services.email_service import (
    file_shared_email,
    files_shared_email,
    notification_email,
)
from app.services.security_events import EVENT_TYPES

RULE_ALERTS = {
    "repeated_failed_logins",
    "repeated_unauthorized_access",
    "excessive_downloads",
    "expired_link_abuse",
    "revoked_link_abuse",
}
ACCOUNT_EVENTS = {
    "new_ip_login": ("New sign-in to your account", "warning"),
    "account_locked": ("Your account was locked", "critical"),
    "repeated_failed_logins": ("Many failed sign-ins on your account", "critical"),
    "token_reuse": ("Your sessions were ended for safety", "critical"),
    "vault_locked": ("Your vault was locked", "critical"),
}
ACCOUNT_MESSAGES = {
    "new_ip_login": "Someone signed in to your account from a new IP address ({ip}). "
    "If this wasn't you, change your password and sign out other devices.",
    "account_locked": "Too many wrong passwords – your account is locked for a few minutes. "
    "If this wasn't you, change your password.",
    "repeated_failed_logins": "There were {count} failed sign-in attempts on your account. "
    "If this wasn't you, change your password and turn on two-step verification.",
    "token_reuse": "An old session token was used again, so every session was ended. "
    "Sign in again and change your password if you didn't expect this.",
    "vault_locked": "Too many wrong vault passwords – your vault is locked for 15 minutes.",
}


def _service() -> NotificationService:
    return NotificationService(get_mongo(), get_redis())


def _app_link(path: str) -> str:
    return f"{get_settings().frontend_url}{path}"


# ---------- activity hook ----------


async def on_activity(activity: dict[str, Any], user: User | None, _: Request | None) -> None:
    action, details = activity["action"], activity.get("details") or {}
    direct = details.get("share_type") == "user" and user is not None
    if action == "share.create" and direct and not details.get("batch"):
        await _file_shared(user, details, activity.get("file_id"))
    elif action == "share.create_batch" and direct:
        await _files_shared(user, details)
    elif action == "share.update" and details.get("share_type") == "user" and user is not None:
        await _access_changed(user, details, activity.get("file_id"))
    elif action == "file.download" and details.get("via") in ("link", "direct_share"):
        await _file_downloaded(activity, user, details)


async def _file_shared(owner: User, details: dict[str, Any], file_id: str | None) -> None:
    recipient = await load_user(details.get("recipient_id") or "")
    if recipient is None or not recipient.is_active:
        return
    file_name = details.get("file_name") or "a file"
    can_download = details.get("permission") == "download"
    expires = details.get("expires_at")
    expires_text = (
        datetime.fromisoformat(expires).strftime("%d %b %Y, %H:%M UTC") if expires else None
    )
    await _service().notify(
        recipient,
        "file_shared",
        "A file was shared with you",
        f"{owner.full_name} shared “{file_name}” with you "
        f"({'view and download' if can_download else 'view only'}).",
        link="/shared-with-me",
        data={"file_id": file_id, "share_id": details.get("share_id"), "owner": owner.email},
        email=file_shared_email(
            to=recipient.email,
            name=recipient.full_name,
            owner_name=owner.full_name,
            owner_email=owner.email,
            file_name=file_name,
            can_download=can_download,
            expires=expires_text,
            link=_app_link("/shared-with-me"),
        ),
    )


async def _files_shared(owner: User, details: dict[str, Any]) -> None:
    recipient = await load_user(details.get("recipient_id") or "")
    if recipient is None or not recipient.is_active:
        return
    names = details.get("file_names") or []
    count = details.get("count") or len(names)
    folder = details.get("folder_name")
    can_download = details.get("permission") == "download"
    expires = details.get("expires_at")
    expires_text = (
        datetime.fromisoformat(expires).strftime("%d %b %Y, %H:%M UTC") if expires else None
    )
    listed = ", ".join(f"“{n}”" for n in names[:3]) + (" …" if count > 3 else "")
    access = "view and download" if can_download else "view only"
    await _service().notify(
        recipient,
        "file_shared",
        "A folder was shared with you" if folder else f"{count} files were shared with you",
        f"{owner.full_name} shared the folder “{folder}” ({count} files) with you ({access})."
        if folder
        else f"{owner.full_name} shared {count} files with you: {listed} ({access}).",
        link="/shared-with-me",
        data={"count": count, "owner": owner.email},
        email=files_shared_email(
            to=recipient.email,
            name=recipient.full_name,
            owner_name=owner.full_name,
            owner_email=owner.email,
            file_names=names,
            folder_name=folder,
            can_download=can_download,
            expires=expires_text,
            link=_app_link("/shared-with-me"),
        ),
    )


async def _access_changed(owner: User, details: dict[str, Any], file_id: str | None) -> None:
    recipient = await load_user(details.get("recipient_id") or "")
    if recipient is None or not recipient.is_active:
        return
    access = "view and download" if details.get("permission") == "download" else "view only"
    expires = details.get("expires_at")
    until = (
        f", until {datetime.fromisoformat(expires).strftime('%d %b %Y, %H:%M UTC')}"
        if expires
        else ", with no expiry"
    )
    file_name = details.get("file_name") or "a file"
    await _service().notify(
        recipient,
        "file_shared",
        "Your access to a shared file changed",
        f"{owner.full_name} changed your access to “{file_name}”: {access}{until}.",
        link="/shared-with-me",
        data={"file_id": file_id, "share_id": details.get("share_id"), "owner": owner.email},
    )


async def _file_downloaded(
    activity: dict[str, Any], visitor: User | None, details: dict[str, Any]
) -> None:
    owner_id = details.get("owner_id")
    if not owner_id or owner_id == activity.get("user_id"):
        return
    file_id = activity.get("file_id")
    cooldown = get_settings().download_notice_cooldown_minutes * 60
    if not await get_redis().set(
        f"notify_download:{owner_id}:{file_id}", "1", nx=True, ex=cooldown
    ):
        return  # already told the owner about this file a moment ago
    owner = await load_user(owner_id)
    if owner is None:
        return
    who = visitor.full_name if visitor else "Someone with the share link"
    file_name = details.get("file_name") or "your file"
    when = activity["created_at"].astimezone(UTC).strftime("%d %b %Y, %H:%M UTC")
    message = f"{who} downloaded “{file_name}” on {when}."
    await _service().notify(
        owner,
        "file_downloaded",
        "Your shared file was downloaded",
        message,
        link="/shared-by-me",
        data={"file_id": file_id, "share_id": details.get("share_id"), "downloaded_at": when},
        email=notification_email(
            owner.email,
            owner.full_name,
            "Your shared file was downloaded",
            message,
            "See your shares",
            _app_link("/shared-by-me"),
            "You can turn these emails off in Settings → Notifications.",
        ),
    )


# ---------- security event hook ----------


async def on_security_event(event: dict[str, Any]) -> None:
    await _alert_admins(event)
    await _alert_account_owner(event)


async def _alert_admins(event: dict[str, Any]) -> None:
    event_type = event["type"]
    if event_type == "admin_action":
        return
    if event_type not in RULE_ALERTS and event["severity"] != "high":
        return  # low/medium events stay on the dashboard without pinging admins
    title = EVENT_TYPES.get(event_type, ("", event_type))[1]
    who = event.get("actor_email") or event.get("ip_address") or "unknown source"
    message = f"{event.get('message') or title} – {who}."
    critical = event["severity"] == "high"
    cooldown = get_settings().admin_alert_email_cooldown_minutes * 60
    send_email = critical and await get_redis().set(
        f"notify_alert_email:{event_type}", "1", nx=True, ex=cooldown
    )
    service = _service()
    for admin in await active_admins():
        await service.notify(
            admin,
            "security_alert",
            f"Security alert: {title}",
            message,
            severity="critical" if critical else "warning",
            link="/admin/security",
            data={"alert_id": event.get("alert_id"), "event_type": event_type},
            email=(
                notification_email(
                    admin.email,
                    admin.full_name,
                    f"Security alert: {title}",
                    message,
                    "Open the Security dashboard",
                    _app_link("/admin/security"),
                    "Sent for high-severity alerts (at most one per type every "
                    f"{cooldown // 60} minutes).",
                )
                if send_email
                else None
            ),
        )


async def _alert_account_owner(event: dict[str, Any]) -> None:
    user_id = event.get("user_id") or (event.get("details") or {}).get("user_id")
    if event["type"] not in ACCOUNT_EVENTS or not user_id:
        return
    user = await load_user(str(user_id))
    if user is None:
        return
    title, severity = ACCOUNT_EVENTS[event["type"]]
    message = ACCOUNT_MESSAGES[event["type"]].format(
        ip=event.get("ip_address") or "unknown",
        count=(event.get("rule") or {}).get("count", "several"),
    )
    await _service().notify(
        user,
        "account_security",
        title,
        message,
        severity=severity,
        link="/settings?tab=devices",
        data={"alert_id": event.get("alert_id"), "event_type": event["type"]},
        email=notification_email(
            user.email,
            user.full_name,
            title,
            message,
            "Review your devices",
            _app_link("/settings?tab=devices"),
            "Security emails can be turned off in Settings → Notifications (not recommended).",
        ),
    )
