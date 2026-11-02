"""The audit log entry and how its human-readable description is written.

An audit entry (MongoDB "audit_logs", append-only):

    log_id         unique ID (UUID)                         – brief: Log ID
    user_id        who                                      – brief: User ID
    username       their name at that moment (or the email tried, for unknown accounts)
    activity_type  login, upload, download, share, …        – brief: Activity Type
    action         the precise action ("file.download")
    file_id        related file, if any                     – brief: File ID
    description    readable sentence – never a file name    – brief: Activity Description
    status         success / failure                        – brief: Activity Status
    ip_address                                              – brief: IP Address
    created_at     (millisecond precision, so the hash survives MongoDB's storage) – Date and Time
    seq            position in the chain (unique)
    prev_hash      hash of the entry before
    hash           SHA-256(prev_hash + canonical JSON of the fields above)

Editing, inserting or deleting any entry changes a hash, so `verify` finds the first broken link.
"""

import hashlib
import json
from typing import Any

GENESIS_HASH = "0" * 64

# Fields that go into the hash, in this order.
HASHED_FIELDS = (
    "log_id",
    "seq",
    "user_id",
    "username",
    "activity_type",
    "action",
    "file_id",
    "description",
    "status",
    "ip_address",
    "created_at",
    "imported",
)


def entry_hash(prev_hash: str, entry: dict[str, Any]) -> str:
    canonical = {field: entry.get(field) for field in HASHED_FIELDS}
    canonical["created_at"] = entry["created_at"].isoformat(timespec="milliseconds")
    payload = json.dumps(canonical, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256((prev_hash + payload).encode()).hexdigest()


# Readable descriptions. Placeholders come from the activity details; names are never used.
DESCRIPTIONS: dict[str, str] = {
    "auth.login.success": "Signed in ({method})",
    "auth.login.failed": "Failed sign-in attempt ({reason})",
    "auth.login.locked": "Sign-in attempt on a locked account",
    "auth.oauth_login": "Google sign-in started",
    "auth.logout": "Signed out",
    "auth.logout_all": "Signed out of all devices",
    "auth.access_denied": "Access denied – missing permission ({permission})",
    "auth.password_changed": "Changed the password",
    "auth.password_reset": "Reset the password by email",
    "auth.password_reset_requested": "Requested a password reset",
    "auth.verify_email": "Verified the email address",
    "auth.mfa_enabled": "Turned on two-step verification",
    "auth.mfa_disabled": "Turned off two-step verification",
    "auth.backup_codes_regenerated": "Generated new backup codes",
    "auth.device_signed_out": "Signed out a device",
    "account.profile_updated": "Updated the profile name",
    "account.deleted": "Deleted the account",
    "file.upload": "Uploaded a file ({size})",
    "file.upload_rejected": "File upload rejected ({reason})",
    "file.download": "Downloaded a file (via {via})",
    "file.download_zip": "Downloaded {count} files as one ZIP ({size})",
    "file.preview": "Opened a file preview",
    "file.access_denied": "Tried to open a file without permission",
    "file.rename": "Renamed a file",
    "file.move": "Moved a file",
    "file.trash": "Moved a file to the trash",
    "file.restore": "Restored a file from the trash",
    "file.delete": "Deleted a file permanently",
    "folder.create": "Created a folder",
    "folder.rename": "Renamed a folder",
    "folder.move": "Moved a folder",
    "folder.trash": "Moved a folder to the trash",
    "folder.restore": "Restored a folder",
    "folder.delete": "Deleted a folder permanently",
    "share.create": "Shared a file ({share_type}, {permission})",
    "share.update": "Changed a share ({changes})",
    "share.revoke": "Revoked a share",
    "share.access_denied": "Share link access denied ({reason})",
    "share.expired": "A share link expired",
    "vault.created": "Created the secure vault",
    "vault.unlock_failed": "Wrong vault password",
    "vault.file_added": "Added a file to the vault ({size})",
    "vault.upload_rejected": "Vault upload rejected ({reason})",
    "vault.file_previewed": "Opened a vault file",
    "vault.file_downloaded": "Downloaded a vault file",
    "vault.file_renamed": "Renamed a vault file",
    "vault.file_deleted": "Deleted a vault file",
    "vault.file_moved_in": "Moved a file into the vault",
    "vault.file_moved_out": "Moved a file out of the vault",
    "vault.password_changed": "Changed the vault password",
    "vault.reset": "Reset the vault",
    "admin.user_update": "Admin changed an account",
    "admin.user_unlock": "Admin unlocked an account",
    "admin.user_delete": "Admin deleted an inactive account",
    "admin.audit_export": "Admin exported the audit log",
    "admin.alert_acknowledged": "Admin acknowledged a security alert ({alert_type})",
    "admin.alert_resolved": "Admin resolved a security alert ({alert_type})",
    "admin.alert_reopened": "Admin reopened a security alert ({alert_type})",
}


def _size(value: Any) -> str:
    try:
        size = float(value)
    except (TypeError, ValueError):
        return "?"
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return "?"


class _Safe(dict):
    """format_map helper: a missing placeholder becomes "–" instead of an error."""

    def __missing__(self, key: str) -> str:
        return "–"


def describe(action: str, details: dict[str, Any] | None) -> str:
    details = details or {}
    values = _Safe({k: v for k, v in details.items() if isinstance(v, str | int | float)})
    values["size"] = _size(details.get("size_bytes"))
    template = DESCRIPTIONS.get(action)
    if template is None:
        return action.replace(".", " ").replace("_", " ").capitalize()
    return template.format_map(values).replace("_", " ")
