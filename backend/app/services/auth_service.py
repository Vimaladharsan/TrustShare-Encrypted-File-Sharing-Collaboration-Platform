"""Registration, login and session refresh rules. All authentication decisions live here."""

import asyncio
import logging
from datetime import UTC, datetime

from redis.asyncio import Redis
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.permissions import RoleName
from app.core.security import (
    create_access_token,
    hash_password,
    spend_password_check_time,
    verify_password,
)
from app.models import User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse
from app.schemas.user import UserResponse
from app.services.login_guard import LoginGuard
from app.services.session_service import SessionService

logger = logging.getLogger(__name__)


# Same message for "no such email" and "wrong password": never reveal which emails exist.
def invalid_credentials() -> AppError:
    return AppError("INVALID_CREDENTIALS", "Invalid email or password.", status_code=401)


class AuthService:
    def __init__(self, session: AsyncSession, redis: Redis) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.sessions = SessionService(redis)
        self.guard = LoginGuard(redis)

    async def register(self, data: RegisterRequest) -> User:
        # TODO (Phase 3D, email verification): return the same response for existing emails
        # to prevent user enumeration.
        if await self.users.get_by_email(data.email):
            raise AppError("EMAIL_TAKEN", "An account with this email already exists.", 409)

        settings = get_settings()
        user = User(
            email=data.email,
            full_name=data.full_name,
            # bcrypt is deliberately slow (~0.25 s); run it in a worker thread so the server
            # keeps answering other requests meanwhile.
            password_hash=await asyncio.to_thread(hash_password, data.password),
            # Every self-registered account is a normal User. Only an Admin can change roles.
            role=await self.users.get_role(RoleName.USER),
            storage_quota_bytes=settings.default_quota_mb * 1024 * 1024,
        )
        try:
            await self.users.add(user)
            await self.session.commit()
        except IntegrityError as exc:  # two sign-ups with the same email at the same moment
            await self.session.rollback()
            raise AppError(
                "EMAIL_TAKEN", "An account with this email already exists.", 409
            ) from exc
        logger.info("User registered: %s", user.id)
        return user

    async def login(
        self, data: LoginRequest, ip: str, user_agent: str
    ) -> tuple[TokenResponse, str]:
        """Returns (access token response, refresh token for the cookie)."""
        user = await self.users.get_by_email(data.email)
        if user is None:
            await asyncio.to_thread(spend_password_check_time, data.password)
            raise invalid_credentials()

        # Checked before the password, so a locked account can't keep being guessed.
        await self.guard.ensure_not_locked(user.id)
        if not await asyncio.to_thread(verify_password, data.password, user.password_hash):
            await self.guard.record_failure(user.id)
            logger.info("Failed login for user %s", user.id)
            raise invalid_credentials()
        if not user.is_active:
            raise AppError("ACCOUNT_DISABLED", "This account has been disabled.", 403)

        await self.guard.clear(user.id)
        user.last_login_at = datetime.now(UTC)
        await self.session.commit()

        refresh_token = await self.sessions.create(user.id, ip, user_agent)
        return self._token_response(user), refresh_token

    async def refresh(
        self, refresh_token: str, ip: str, user_agent: str
    ) -> tuple[TokenResponse, str]:
        """Rotate the refresh token and issue a new access token."""
        new_refresh_token, user_id = await self.sessions.rotate(refresh_token, ip, user_agent)
        user = await self.users.get_by_id(user_id)
        if user is None or not user.is_active:
            await self.sessions.revoke(new_refresh_token)
            raise AppError("INVALID_SESSION", "Your session has expired. Please log in again.", 401)
        return self._token_response(user), new_refresh_token

    @staticmethod
    def _token_response(user: User) -> TokenResponse:
        token, expires_in = create_access_token(user.id, user.role.name)
        return TokenResponse(
            access_token=token, expires_in=expires_in, user=UserResponse.from_user(user)
        )
