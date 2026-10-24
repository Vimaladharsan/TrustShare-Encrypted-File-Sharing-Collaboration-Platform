"""Registration, login and session refresh rules. All authentication decisions live here."""

import asyncio
import logging
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import Request
from redis.asyncio import Redis
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.permissions import RoleName
from app.core.rate_limit import client_ip
from app.core.security import (
    create_access_token,
    hash_password,
    spend_password_check_time,
    verify_password,
)
from app.models import User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse
from app.schemas.mfa import MfaRequiredResponse, MfaVerifyRequest
from app.schemas.user import UserResponse
from app.services.activity_service import ActivityService
from app.services.login_guard import LoginGuard
from app.services.mfa_service import MfaService
from app.services.security_events import record_security_event
from app.services.session_service import SessionService

logger = logging.getLogger(__name__)

SUSPICIOUS_FAILURES = 3  # wrong passwords/codes in a row → security event (lockout at 5)
SUSPICIOUS_IP_FAILURES = 10  # failed sign-ins from one IP within 15 minutes


# Same message for "no such email" and "wrong password": never reveal which emails exist.
def invalid_credentials() -> AppError:
    return AppError("INVALID_CREDENTIALS", "Invalid email or password.", status_code=401)


class AuthService:
    def __init__(
        self,
        session: AsyncSession,
        redis: Redis,
        activity: ActivityService | None = None,
        request: Request | None = None,
    ) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.sessions = SessionService(redis)
        self.guard = LoginGuard(redis)
        self.mfa = MfaService(session, redis)
        # Login history goes to the activity log (when the caller provides one).
        self.activity = activity
        self.request = request

    async def _log(
        self,
        user: User | None,
        action: str,
        status: str = "success",
        details: dict[str, str] | None = None,
    ) -> None:
        if self.activity is not None and self.request is not None:
            await self.activity.log(
                self.request, user, action, resource_type="user", status=status, details=details
            )

    async def _failed(self, user: User | None, reason: str, email: str | None = None) -> None:
        details = {"reason": reason}
        if email:
            details["email"] = email  # who was tried, even if no such account exists
        await self._log(user, "auth.login.failed", "failure", details)
        await self._watch_ip()

    async def _ensure_not_locked(self, user: User) -> None:
        try:
            await self.guard.ensure_not_locked(user.id)
        except AppError:
            await self._log(user, "auth.login.locked", "failure")
            await record_security_event(
                "blocked_request",
                request=self.request,
                user=user,
                message="Sign-in attempt on a locked account",
            )
            raise

    async def _count_failure(self, user: User) -> None:
        """Wrong password or code: count it, and raise security events at 3 failures / lockout."""
        failures, locked = await self.guard.record_failure(user.id)
        if locked:
            await record_security_event(
                "account_locked", request=self.request, user=user, details={"attempts": failures}
            )
        elif failures == SUSPICIOUS_FAILURES:
            await record_security_event(
                "multiple_failed_logins",
                request=self.request,
                user=user,
                details={"attempts": failures},
            )

    async def _watch_ip(self) -> None:
        """Many failed sign-ins from one IP within 15 minutes (e.g. trying many accounts)."""
        if self.activity is None or self.request is None:
            return
        ip = client_ip(self.request)
        recent = await self.activity.logs.count_documents(
            {
                "action": "auth.login.failed",
                "ip_address": ip,
                "created_at": {"$gte": datetime.now(UTC) - timedelta(minutes=15)},
            }
        )
        if recent == SUSPICIOUS_IP_FAILURES:  # once, when the threshold is crossed
            await record_security_event(
                "suspicious_ip", request=self.request, details={"failed_logins_15min": recent}
            )

    async def _watch_new_ip(self, user: User) -> None:
        """A successful sign-in from an IP this account never signed in from before."""
        if self.activity is None or self.request is None:
            return
        ip = client_ip(self.request)
        logs = self.activity.logs
        previous = {"user_id": str(user.id), "action": "auth.login.success"}
        if await logs.find_one(previous) and not await logs.find_one(
            {**previous, "ip_address": ip}
        ):
            await record_security_event("new_ip_login", request=self.request, user=user)

    async def register(self, data: RegisterRequest) -> tuple[User, bool]:
        """Returns (user, created). For an email that's already registered nothing is created
        and (existing user, False) is returned – the API answers the same either way, so
        sign-up can't be used to find out who has an account."""
        existing = await self.users.get_by_email(data.email)
        if existing is not None:
            # Spend the same bcrypt time as a real sign-up, so timing reveals nothing either.
            await asyncio.to_thread(hash_password, data.password)
            return existing, False

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
        except IntegrityError:  # two sign-ups with the same email at the same moment
            await self.session.rollback()
            existing = await self.users.get_by_email(data.email)
            if existing is None:
                raise
            return existing, False
        logger.info("User registered: %s", user.id)
        return user, True

    async def login(
        self, data: LoginRequest, ip: str, user_agent: str
    ) -> tuple[TokenResponse | MfaRequiredResponse, str | None]:
        """Returns (tokens, refresh token for the cookie), or (MFA challenge, None)."""
        user = await self.users.get_by_email(data.email)
        if user is None:
            await asyncio.to_thread(spend_password_check_time, data.password)
            await self._failed(None, "unknown_email", str(data.email))
            raise invalid_credentials()

        # Checked before the password, so a locked account can't keep being guessed.
        await self._ensure_not_locked(user)
        if not await asyncio.to_thread(verify_password, data.password, user.password_hash):
            await self._count_failure(user)
            logger.info("Failed login for user %s", user.id)
            await self._failed(user, "wrong_password")
            raise invalid_credentials()
        if not user.is_active:
            await self._failed(user, "account_disabled")
            raise AppError("ACCOUNT_DISABLED", "This account has been disabled.", 403)
        if get_settings().require_email_verification and not user.is_email_verified:
            await self._failed(user, "email_not_verified")
            raise AppError(
                "EMAIL_NOT_VERIFIED",
                "Please verify your email first – use the link we sent when you signed up.",
                403,
            )

        await self.guard.clear(user.id)
        if user.mfa_enabled:
            # Password is correct, but no tokens yet: the second factor is still needed.
            challenge_id, expires_in = await self.mfa.create_challenge(user.id)
            return MfaRequiredResponse(challenge_id=challenge_id, expires_in=expires_in), None
        return await self._complete_login(user, ip, user_agent, "password")

    async def verify_mfa(
        self, data: MfaVerifyRequest, ip: str, user_agent: str
    ) -> tuple[TokenResponse, str]:
        """Second login step: check the authenticator (or backup) code for a challenge."""
        expired = AppError(
            "MFA_CHALLENGE_EXPIRED", "Your sign-in attempt expired. Please log in again.", 401
        )
        user_id = await self.mfa.user_for_challenge(data.challenge_id)
        if user_id is None:
            raise expired
        user = await self.users.get_by_id(user_id)
        if user is None or not user.is_active:
            raise expired

        # Wrong codes count towards the same lockout as wrong passwords.
        await self._ensure_not_locked(user)
        if not await self.mfa.verify_code(user, data.code):
            await self._count_failure(user)
            await self._failed(user, "wrong_mfa_code")
            raise AppError("INVALID_MFA_CODE", "That code is not valid. Please try again.", 401)

        await self.mfa.finish_challenge(data.challenge_id)
        await self.guard.clear(user.id)
        return await self._complete_login(user, ip, user_agent, "password + 2-step code")

    async def start_session(
        self, user: User, ip: str, user_agent: str, method: str
    ) -> tuple[TokenResponse, str]:
        """Used by other ways of logging in (Google, password change) once the user is known."""
        return await self._complete_login(user, ip, user_agent, method)

    async def _complete_login(
        self, user: User, ip: str, user_agent: str, method: str
    ) -> tuple[TokenResponse, str]:
        user.last_login_at = datetime.now(UTC)
        await self.session.commit()  # also saves a used backup code, if one was used
        session_id = uuid.uuid4().hex  # one id per device, kept across token rotation
        refresh_token = await self.sessions.create(user.id, ip, user_agent, family=session_id)
        await self._watch_new_ip(user)  # before logging this sign-in
        await self._log(user, "auth.login.success", details={"method": method})
        return self._token_response(user, session_id), refresh_token

    async def refresh(
        self, refresh_token: str, ip: str, user_agent: str
    ) -> tuple[TokenResponse, str]:
        """Rotate the refresh token and issue a new access token."""
        new_refresh_token, user_id, session_id = await self.sessions.rotate(
            refresh_token, ip, user_agent
        )
        user = await self.users.get_by_id(user_id)
        if user is None or not user.is_active:
            await self.sessions.revoke(new_refresh_token)
            raise AppError("INVALID_SESSION", "Your session has expired. Please log in again.", 401)
        return self._token_response(user, session_id), new_refresh_token

    @staticmethod
    def _token_response(user: User, session_id: str | None = None) -> TokenResponse:
        token, expires_in = create_access_token(user.id, user.role.name, session_id)
        return TokenResponse(
            access_token=token, expires_in=expires_in, user=UserResponse.from_user(user)
        )
