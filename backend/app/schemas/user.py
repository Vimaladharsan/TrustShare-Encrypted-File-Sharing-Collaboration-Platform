import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

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
    """A user as seen on the admin page: also shows lockout and inactivity."""

    is_locked: bool = False
    inactive_days: int = 0  # days since the last login (or sign-up)
    can_delete: bool = False  # inactive long enough (and not an admin) to be deleted


class AdminUserListResponse(BaseModel):
    items: list[AdminUserResponse]
    total: int


class AdminUserUpdate(BaseModel):
    """Fields an admin may change. Anything left out stays as it is."""

    role: RoleName | None = None
    is_active: bool | None = None


# ---------- my own account ----------


class ProfileUpdate(BaseModel):
    full_name: str = Field(min_length=2, max_length=100, examples=["Vimal S"])

    @field_validator("full_name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = " ".join(value.split())  # trim and collapse repeated spaces (same as sign-up)
        if len(value) < 2:
            raise ValueError("Name is too short")
        return value


class DeviceSession(BaseModel):
    """One signed-in device (a session) as shown on the Devices tab."""

    id: str  # the session id – used to sign this device out
    browser: str
    os: str
    kind: str  # desktop | mobile
    ip_address: str
    location: str
    signed_in_at: datetime
    last_active_at: datetime
    current: bool  # the device making this request


class DeviceSessionList(BaseModel):
    items: list[DeviceSession]


class DeleteAccountRequest(BaseModel):
    """Password (if the account has one), a two-step code (if it is on), and a typed
    confirmation: "DELETE" – or, for accounts without a password, the account's email."""

    password: str | None = Field(None, max_length=128)
    code: str | None = Field(None, max_length=20)
    confirm: str = Field(min_length=1, max_length=320)
