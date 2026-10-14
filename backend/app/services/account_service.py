"""Changes a logged-in user makes to their own account (currently: changing the password).

Changing the password logs the account out on every other device (all sessions revoked, older
access tokens rejected), then starts a fresh session for this device so the user stays logged in.
"""

import asyncio
from datetime import UTC, datetime

from fastapi import Request
from pymongo.asynchronous.database import AsyncDatabase
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.rate_limit import client_ip
from app.core.security import hash_password, verify_password
from app.models import User
from app.schemas.auth import TokenResponse, password_problem
from app.services.activity_service import ActivityService
from app.services.auth_service import AuthService
from app.services.session_service import SessionService


class AccountService:
    def __init__(
        self, session: AsyncSession, redis: Redis, db: AsyncDatabase, request: Request
    ) -> None:
        self.session = session
        self.redis = redis
        self.activity = ActivityService(db)
        self.request = request

    async def change_password(
        self, user: User, current_password: str, new_password: str
    ) -> tuple[TokenResponse, str]:
        if user.password_hash is None:
            # Accounts created with Google have no password to confirm; the emailed reset link
            # proves ownership of the email instead.
            raise AppError(
                "NO_PASSWORD",
                'You sign in with Google. Use "Forgot password" on the login page to set one.',
                400,
            )
        # 400, not 401: the session is fine, only the typed password is wrong.
        if not await asyncio.to_thread(verify_password, current_password, user.password_hash):
            raise AppError("WRONG_PASSWORD", "Your current password is incorrect.", 400)
        if current_password == new_password:
            raise AppError("SAME_PASSWORD", "Pick a new password, not the current one.", 400)
        problem = password_problem(new_password, user.email)
        if problem:
            raise AppError("WEAK_PASSWORD", problem, 422)

        user.password_hash = await asyncio.to_thread(hash_password, new_password)
        user.password_changed_at = datetime.now(UTC)  # tokens issued before this stop working
        await self.session.commit()
        await SessionService(self.redis).revoke_all(user.id)  # every device logged out…
        await self.activity.log(self.request, user, "auth.password_changed", resource_type="user")

        # …then a new session for this device, so the user isn't thrown out here too.
        auth = AuthService(self.session, self.redis)
        return await auth.start_session(
            user,
            client_ip(self.request),
            self.request.headers.get("user-agent", ""),
            "password change",
        )
