"""Reusable dependencies for routes: who is calling, and are they allowed?"""

import uuid
from collections.abc import Awaitable, Callable

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.permissions import Perm
from app.core.security import decode_access_token
from app.db.postgres import get_db
from app.models import User
from app.repositories.user_repository import UserRepository

# Reads "Authorization: Bearer <token>". auto_error=False so we return our own error format.
bearer_scheme = HTTPBearer(auto_error=False, description="Paste the access_token from /login")


def _unauthorized(code: str, message: str) -> AppError:
    return AppError(code, message, status_code=401, headers={"WWW-Authenticate": "Bearer"})


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_db),
) -> User:
    """401 if there is no valid token; otherwise the logged-in user, loaded fresh from the DB."""
    if credentials is None:
        raise _unauthorized("NOT_AUTHENTICATED", "Please log in.")
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = uuid.UUID(payload["sub"])
    except (jwt.InvalidTokenError, ValueError) as exc:
        # Expired, tampered with, signed with another key, or malformed.
        raise _unauthorized("INVALID_TOKEN", "Your session is invalid or has expired.") from exc

    # Loading the user on every request means a role change or deactivation applies immediately.
    user = await UserRepository(session).get_by_id(user_id)
    if user is None or not user.is_active:
        raise _unauthorized("INVALID_TOKEN", "Your session is invalid or has expired.")

    # Tokens issued before the last password change are no longer accepted.
    if user.password_changed_at and payload["iat"] < user.password_changed_at.timestamp():
        raise _unauthorized("INVALID_TOKEN", "Your session is invalid or has expired.")
    return user


def require_permission(permission: Perm) -> Callable[..., Awaitable[User]]:
    """Route guard: 401 if not logged in, 403 if the user's role lacks this permission."""

    async def checker(user: User = Depends(get_current_user)) -> User:
        if permission not in user.permission_codes:
            raise AppError("FORBIDDEN", "You don't have permission to do this.", status_code=403)
        return user

    return checker
