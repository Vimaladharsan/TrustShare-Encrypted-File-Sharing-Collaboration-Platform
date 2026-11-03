"""What an activity record looks like, how actions are grouped, and what admins may not see.

An activity record (MongoDB "activity_logs") – the brief's fields plus a few useful extras:

    _id            activity ID (MongoDB ObjectId)
    user_id        who did it (None for anonymous visitors / unknown emails)
    actor_email    their email at that moment
    action         precise action, e.g. "file.download", "auth.login.failed"
    activity_type  the brief's category: login, logout, upload, download, access, share, …
    file_id        the related file, if any
    status         "success" or "failure"
    ip_address, user_agent, request_id, details, created_at
"""

from typing import Any

COLLECTION = "activity_logs"

# Checked in order; the first matching prefix wins.
_TYPE_RULES: list[tuple[str, str]] = [
    ("auth.login", "login"),
    ("auth.oauth_login", "login"),
    ("auth.logout", "logout"),
    ("auth.access_denied", "unauthorized"),
    ("auth.", "account"),
    ("account.", "account"),
    ("file.upload", "upload"),
    ("vault.file_added", "upload"),
    ("vault.upload_rejected", "upload"),
    ("file.download", "download"),
    ("vault.file_downloaded", "download"),
    ("file.preview", "access"),
    ("vault.file_previewed", "access"),
    ("file.access_denied", "unauthorized"),
    ("vault.unlock_failed", "unauthorized"),
    ("share.access_denied", "link_access"),
    ("share.", "share"),
    ("file.", "file_management"),
    ("folder.", "file_management"),
    ("vault.", "vault"),
    ("admin.", "admin"),
]
ACTIVITY_TYPES = sorted({activity_type for _, activity_type in _TYPE_RULES} | {"other"})


def activity_type_of(action: str) -> str:
    return next((kind for prefix, kind in _TYPE_RULES if action.startswith(prefix)), "other")


# Admins never see the names of users' files or folders (privacy rule, Milestone 2) – these
# detail keys are removed from everything shown to an admin. Owners still see their own names.
PRIVATE_DETAIL_KEYS = frozenset({"file_name", "file_names", "original_name", "name", "from", "to"})


def redact(details: dict[str, Any] | None) -> dict[str, Any]:
    return {k: v for k, v in (details or {}).items() if k not in PRIVATE_DETAIL_KEYS}
