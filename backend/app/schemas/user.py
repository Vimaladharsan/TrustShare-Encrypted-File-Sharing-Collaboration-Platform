import uuid
from datetime import datetime

from pydantic import BaseModel

from app.core.permissions import RoleName
from app.models import User


class UserResponse(BaseModel):
    """What the API returns about a user. Never includes the password hash or MFA secret."""

    id: uuid.UUID
    email: str
    full_name: str
    role: str
    permissions: list[str]
    is_active: bool
    is_email_verified: bool
    mfa_enabled: bool
    has_password: bool  # False for accounts created with Google (they log in with Google)
    created_at: datetime
    last_login_at: datetime | None

    @classmethod
    def from_user(cls, user: User) -> "UserResponse":
        return cls(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=user.role.name,
            permissions=sorted(user.permission_codes),
            is_active=user.is_active,
            is_email_verified=user.is_email_verified,
            mfa_enabled=user.mfa_enabled,
            has_password=user.password_hash is not None,
            created_at=user.created_at,
            last_login_at=user.last_login_at,
        )


# ---------- admin user management ----------


class AdminUserResponse(UserResponse):
    """A user as seen on the admin page: also shows whether the account is locked out."""

    is_locked: bool = False


class AdminUserListResponse(BaseModel):
    items: list[AdminUserResponse]
    total: int


class AdminUserUpdate(BaseModel):
    """Fields an admin may change. Anything left out stays as it is."""

    role: RoleName | None = None
    is_active: bool | None = None
