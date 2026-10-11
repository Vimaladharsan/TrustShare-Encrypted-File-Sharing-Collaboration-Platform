import uuid
from datetime import datetime

from pydantic import BaseModel

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
            created_at=user.created_at,
            last_login_at=user.last_login_at,
        )


class UserListResponse(BaseModel):
    items: list[UserResponse]
    total: int
