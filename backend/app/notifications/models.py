"""Notification types and the stored shape (MongoDB "notifications").

A notification (the brief's fields + delivery details):

    _id           notification ID
    user_id       recipient
    type          see TYPES below
    title         short headline              message   one sentence
    severity      info | warning | critical   link      where it leads in the app
    data          ids (file_id, share_id, alert_id …) – never file contents
    read          False until marked read     read_at
    email_status  sent | failed | skipped (turned off) | none (in-app only)
    created_at

Preferences (MongoDB "notification_preferences"): {user_id, email: {<type>: bool}}.
"""

from dataclasses import dataclass

COLLECTION = "notifications"
PREFERENCES = "notification_preferences"


@dataclass(frozen=True)
class NotificationType:
    label: str  # shown in the preferences page
    email_default: bool  # also send an email unless the user turned it off
    email_optional: bool = True  # False = in-app only, no email setting


TYPES: dict[str, NotificationType] = {
    "file_shared": NotificationType("Someone shares a file with me", True),
    "file_downloaded": NotificationType("Someone downloads a file I shared", False),
    "link_expiring": NotificationType("A share link is about to expire", True),
    "link_expired": NotificationType("A share link has expired", False, email_optional=False),
    "account_security": NotificationType("Security events on my account", True),
    "security_alert": NotificationType("Security alerts (administrators)", True),
}


def channel(user_id: str) -> str:
    """Redis pub/sub channel that the user's live stream listens to."""
    return f"notifications:{user_id}"
