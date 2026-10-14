"""Forgot password → emailed link → choose a new password.

Redis keys (expire automatically):
    pwd_reset:{sha256(token)}   -> user_id   (15 min, single use: read and deleted in one step)
    pwd_reset_user:{user_id}    -> hash of the latest token (a new request cancels the old link)

Rules:
  - the API answers the same whether or not the email exists (no account discovery)
  - the link works once and expires after 15 minutes; only its hash is stored
  - a successful reset logs the user out everywhere and clears any lockout
"""

import asyncio
import logging
import uuid
from datetime import UTC, datetime

from fastapi import Request
from pymongo.asynchronous.database import AsyncDatabase
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.security import hash_password, hash_token, new_url_token
from app.repositories.user_repository import UserRepository
from app.schemas.auth import password_problem
from app.services.activity_service import ActivityService
from app.services.email_service import Email, password_reset_email
from app.services.login_guard import LoginGuard
from app.services.session_service import SessionService

logger = logging.getLogger(__name__)


def _invalid_link() -> AppError:
    return AppError(
        "INVALID_RESET_LINK",
        "This reset link is invalid or has expired. Please ask for a new one.",
        400,
    )


class PasswordResetService:
    def __init__(
        self, session: AsyncSession, redis: Redis, db: AsyncDatabase, request: Request
    ) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.redis = redis
        self.activity = ActivityService(db)
        self.request = request

    async def request_reset(self, email: str) -> Email | None:
        """Creates a reset link if the account exists. Returns the email to send (or None)."""
        user = await self.users.get_by_email(email)
        if user is None or not user.is_active:
            logger.info("Password reset requested for unknown or disabled email")
            return None

        settings = get_settings()
        ttl = settings.password_reset_minutes * 60
        token = new_url_token()
        token_hash = hash_token(token)

        # Only the newest link is valid: delete the previous one, if any.
        old_hash = await self.redis.get(f"pwd_reset_user:{user.id}")
        async with self.redis.pipeline(transaction=True) as pipe:
            if old_hash:
                pipe.delete(f"pwd_reset:{old_hash}")
            pipe.set(f"pwd_reset:{token_hash}", str(user.id), ex=ttl)
            pipe.set(f"pwd_reset_user:{user.id}", token_hash, ex=ttl)
            await pipe.execute()

        await self.activity.log(self.request, user, "auth.password_reset_requested")
        link = f"{settings.frontend_url}/reset-password?token={token}"
        minutes = settings.password_reset_minutes
        return password_reset_email(user.email, user.full_name, link, minutes)

    async def reset(self, token: str, new_password: str) -> None:
        token_hash = hash_token(token)
        # Look first (without using it up), so a too-weak password doesn't waste the link.
        user_id = await self.redis.get(f"pwd_reset:{token_hash}")
        if user_id is None:
            raise _invalid_link()
        user = await self.users.get_by_id(uuid.UUID(user_id))
        if user is None or not user.is_active:
            raise _invalid_link()

        problem = password_problem(new_password, user.email)
        if problem:
            raise AppError("WEAK_PASSWORD", problem, 422)

        # Now use the link up – GETDEL is atomic, so two requests can't both succeed.
        if await self.redis.getdel(f"pwd_reset:{token_hash}") is None:
            raise _invalid_link()
        await self.redis.delete(f"pwd_reset_user:{user.id}")

        user.password_hash = await asyncio.to_thread(hash_password, new_password)
        user.password_changed_at = datetime.now(UTC)  # tokens issued before this stop working
        await self.session.commit()

        await SessionService(self.redis).revoke_all(user.id)  # logged out on every device
        await LoginGuard(self.redis).unlock(user.id)  # a forgotten password often caused a lockout
        await self.activity.log(self.request, user, "auth.password_reset")
        logger.info("Password reset for user %s", user.id)
