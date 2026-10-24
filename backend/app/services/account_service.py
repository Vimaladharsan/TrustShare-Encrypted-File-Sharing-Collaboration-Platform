"""Changes a logged-in user makes to their own account: profile name, password, signed-in
devices, and deleting the account.

Changing the password logs the account out on every other device (all sessions revoked, older
access tokens rejected), then starts a fresh session for this device so the user stays logged in.
Deleting the account needs the password, a two-step code (if on) and a typed confirmation.
"""

import asyncio
from datetime import UTC, datetime

from fastapi import Request
from pymongo.asynchronous.database import AsyncDatabase
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.permissions import RoleName
from app.core.rate_limit import client_ip
from app.core.security import hash_password, verify_password
from app.core.user_agent import describe_device
from app.models import User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import TokenResponse, password_problem
from app.schemas.user import DeleteAccountRequest, DeviceSession
from app.services.account_deletion import erase_account
from app.services.activity_service import ActivityService
from app.services.admin_reports_service import ip_location
from app.services.auth_service import AuthService
from app.services.mfa_service import MfaService
from app.services.session_service import SessionService
from app.storage.secure_store import SecureFileStore


class AccountService:
    def __init__(
        self, session: AsyncSession, redis: Redis, db: AsyncDatabase, request: Request
    ) -> None:
        self.session = session
        self.redis = redis
        self.activity = ActivityService(db)
        self.request = request

    # ---------- profile ----------

    async def update_profile(self, user: User, full_name: str) -> User:
        if full_name != user.full_name:
            old = user.full_name
            user.full_name = full_name
            await self.session.commit()
            await self.activity.log(
                self.request,
                user,
                "account.profile_updated",
                resource_type="user",
                details={"from": old, "to": full_name},
            )
        return user

    # ---------- devices ----------

    async def devices(self, user: User, current_session: str | None) -> list[DeviceSession]:
        result = []
        for s in await SessionService(self.redis).list_devices(user.id):
            device = describe_device(s.get("user_agent", ""))
            result.append(
                DeviceSession(
                    id=s["family"],
                    browser=device["browser"],
                    os=device["os"],
                    kind=device["kind"],
                    ip_address=s.get("ip", ""),
                    location=ip_location(s.get("ip")),
                    signed_in_at=_from_epoch(s.get("signed_in_at", s["created_at"])),
                    last_active_at=_from_epoch(s["created_at"]),
                    current=s["family"] == current_session,
                )
            )
        return result

    async def sign_out_device(self, user: User, session_id: str) -> None:
        if not await SessionService(self.redis).revoke_device(user.id, session_id):
            raise AppError("SESSION_NOT_FOUND", "That device is not signed in any more.", 404)
        await self.activity.log(
            self.request,
            user,
            "auth.device_signed_out",
            resource_type="user",
            details={"session": session_id[:8]},
        )

    # ---------- delete my account ----------

    async def delete_account(
        self, user: User, data: DeleteAccountRequest, storage: SecureFileStore, db: AsyncDatabase
    ) -> dict:
        if user.password_hash is not None:
            if data.confirm != "DELETE":
                raise AppError("CONFIRMATION_MISMATCH", "Type DELETE to confirm.", 400)
            if not data.password or not await asyncio.to_thread(
                verify_password, data.password, user.password_hash
            ):
                raise AppError("WRONG_PASSWORD", "Your password is incorrect.", 400)
        elif data.confirm.strip().lower() != user.email.lower():
            # Google-only accounts have no password: typing the email confirms instead.
            raise AppError("CONFIRMATION_MISMATCH", "Type your email address to confirm.", 400)
        if user.mfa_enabled and not await MfaService(self.session, self.redis).verify_code(
            user, data.code or ""
        ):
            raise AppError("INVALID_MFA_CODE", "That two-step code is not valid.", 400)
        if user.role.name == RoleName.ADMIN:
            admins = await UserRepository(self.session).count_active_with_role(RoleName.ADMIN)
            if admins <= 1:
                raise AppError(
                    "LAST_ADMIN",
                    "You are the last admin. Make someone else an admin first.",
                    409,
                )

        email, name = user.email, user.full_name
        # Logged before the account disappears, so the audit trail keeps who and when.
        await self.activity.log(self.request, user, "account.deleted", resource_type="user")
        erased = await erase_account(
            user, session=self.session, db=db, redis=self.redis, storage=storage
        )
        return {"email": email, "name": name, **erased}

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


def _from_epoch(value: str) -> datetime:
    return datetime.fromtimestamp(int(value), tz=UTC)
