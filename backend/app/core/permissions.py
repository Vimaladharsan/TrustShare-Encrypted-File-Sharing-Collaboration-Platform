"""Permission codes and role names, matching the rows seeded by the first migration.

Routes check permissions (not role names), so a new role never needs code changes.
"""

from enum import StrEnum


class Perm(StrEnum):
    FILE_READ = "file:read"
    FILE_UPLOAD = "file:upload"
    FILE_UPDATE = "file:update"
    FILE_DELETE = "file:delete"
    FOLDER_MANAGE = "folder:manage"
    FILE_READ_ALL = "file:read_all"
    USER_READ = "user:read"
    USER_MANAGE = "user:manage"
    AUDIT_READ = "audit:read"
    SHARE_CREATE = "share:create"


class RoleName(StrEnum):
    ADMIN = "admin"
    USER = "user"
    GUEST = "guest"
