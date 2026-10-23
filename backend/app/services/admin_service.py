"""User management by admins: change roles, enable/disable accounts, unlock lockouts, and delete
accounts that have been inactive for a long time.

Safety rules:
  - admins can't change their own role or disable themselves (no accidental self-lockout)
  - the last active admin can never be removed, so the system always has someone in charge
  - disabling an account logs it out of every device immediately
  - admins never get access to other users' files (privacy); the only thing they can do with
    them is delete them together with an account that hasn't logged in for
    INACTIVE_ACCOUNT_DAYS (default 30) - admin accounts themselves can't be deleted this way
Every change is written to the activity log (which is kept even after an account is deleted).
"""

import uuid
from datetime import UTC, datetime

from fastapi import Request
from pymongo.asynchronous.database import AsyncDatabase
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.permissions import RoleName
from app.models import User
from app.repositories.favorite_repository import FavoriteRepository
from app.repositories.file_repository import FileRepository
from app.repositories.folder_repository import FolderRepository
from app.repositories.user_repository import UserRepository
from app.schemas.user import AdminUserResponse, AdminUserUpdate, UserResponse
from app.services.activity_service import ActivityService
from app.services.login_guard import LoginGuard
from app.services.security_events import record_security_event
from app.services.session_service import SessionService
from app.storage.secure_store import SecureFileStore


def _not_found() -> AppError:
    return AppError("USER_NOT_FOUND", "User not found.", 404)


class AdminService:
    def __init__(
        self,
        session: AsyncSession,
        redis: Redis,
        db: AsyncDatabase,
        request: Request,
        storage: SecureFileStore | None = None,
    ) -> None:
        self.session = session
        self.db = db
        self.storage = storage
        self.users = UserRepository(session)
        self.redis = redis
        self.guard = LoginGuard(redis)
        self.activity = ActivityService(db)
        self.request = request

    async def list_users(
        self, search: str | None, limit: int, offset: int
    ) -> tuple[list[AdminUserResponse], int]:
        users, total = await self.users.list_users(search, limit, offset)
        locked = await self.guard.locked_ids([user.id for user in users])
        return [_to_response(user, user.id in locked) for user in users], total

    async def update_user(
        self, admin: User, user_id: uuid.UUID, data: AdminUserUpdate
    ) -> AdminUserResponse:
        user = await self.users.get_by_id(user_id)
        if user is None:
            raise _not_found()

        changes: dict[str, object] = {}
        if data.role is not None and data.role != user.role.name:
            changes["role"] = {"from": user.role.name, "to": data.role.value}
        if data.is_active is not None and data.is_active != user.is_active:
            changes["is_active"] = {"from": user.is_active, "to": data.is_active}
        if not changes:
            return await self._response(user)

        if user.id == admin.id:
            raise AppError(
                "CANNOT_CHANGE_SELF",
                "You can't change your own role or disable your own account.",
                400,
            )
        removes_admin = user.role.name == RoleName.ADMIN and user.is_active
        if removes_admin and await self.users.count_active_with_role(RoleName.ADMIN) <= 1:
            raise AppError("LAST_ADMIN", "The last active admin can't be removed.", 409)

        if "role" in changes:
            user.role = await self.users.get_role(data.role)
        if "is_active" in changes:
            user.is_active = data.is_active
        await self.session.commit()

        if data.is_active is False:
            await SessionService(self.redis).revoke_all(user.id)  # logged out everywhere now
        await self.activity.log(
            self.request,
            admin,
            "admin.user_update",
            resource_type="user",
            resource_id=str(user.id),
            details={"email": user.email, "changes": changes},
        )
        await self._admin_event(admin, f"Changed account {user.email}", changes)
        return await self._response(user)

    async def unlock(self, admin: User, user_id: uuid.UUID) -> AdminUserResponse:
        user = await self.users.get_by_id(user_id)
        if user is None:
            raise _not_found()
        await self.guard.unlock(user.id)
        await self.activity.log(
            self.request,
            admin,
            "admin.user_unlock",
            resource_type="user",
            resource_id=str(user.id),
            details={"email": user.email},
        )
        await self._admin_event(admin, f"Unlocked account {user.email}", {})
        return await self._response(user)

    async def delete_inactive(self, admin: User, user_id: uuid.UUID) -> None:
        """Delete an account that hasn't logged in for INACTIVE_ACCOUNT_DAYS, with all its files:
        encrypted objects, keys, metadata, folders and sessions. Cannot be undone."""
        user = await self.users.get_by_id(user_id)
        if user is None:
            raise _not_found()
        if user.id == admin.id:
            raise AppError("CANNOT_DELETE_SELF", "You can't delete your own account.", 400)
        if user.role.name == RoleName.ADMIN:
            raise AppError(
                "CANNOT_DELETE_ADMIN",
                "Admin accounts can't be deleted. Change the role to User first.",
                400,
            )
        days, limit = inactive_days(user), get_settings().inactive_account_days
        if days < limit:
            raise AppError(
                "ACCOUNT_STILL_ACTIVE",
                f"This account was last active {days} day(s) ago. Accounts can only be deleted "
                f"after {limit} days without a login.",
                409,
            )
        if self.storage is None:
            raise RuntimeError("AdminService needs a SecureFileStore to delete accounts")

        owner_id, email = str(user.id), user.email
        files = await FileRepository(self.db).all_owned(owner_id)
        for doc in files:  # safe to repeat if interrupted: deleting a missing object is a no-op
            await self.storage.delete(doc)  # encrypted object + its key (crypto-shredding)
        await FileRepository(self.db).delete_all_owned(owner_id)
        await FolderRepository(self.db).delete_all_owned(owner_id)
        await FavoriteRepository(self.db).delete_for_user(owner_id)

        await self.users.delete(user_id)
        await self.session.commit()
        await SessionService(self.redis).revoke_all(user_id)
        await self.guard.unlock(user_id)
        await self.activity.log(
            self.request,
            admin,
            "admin.user_delete",
            resource_type="user",
            resource_id=owner_id,
            details={
                "email": email,
                "inactive_days": days,
                "files_deleted": len(files),
                "bytes_freed": sum(doc["size_bytes"] for doc in files),
            },
        )
        await self._admin_event(
            admin, f"Deleted inactive account {email}", {"files_deleted": len(files)}
        )

    async def _admin_event(self, admin: User, message: str, details: dict) -> None:
        await record_security_event(
            "admin_action", request=self.request, user=admin, message=message, details=details
        )

    async def _response(self, user: User) -> AdminUserResponse:
        locked = await self.guard.locked_ids([user.id])
        return _to_response(user, user.id in locked)


def inactive_days(user: User) -> int:
    """Whole days since the last login (or since sign-up, if the user never logged in)."""
    last_seen = user.last_login_at or user.created_at
    return max((datetime.now(UTC) - last_seen).days, 0)


def _to_response(user: User, is_locked: bool) -> AdminUserResponse:
    days = inactive_days(user)
    return AdminUserResponse(
        **UserResponse.from_user(user).model_dump(),
        is_locked=is_locked,
        inactive_days=days,
        can_delete=(
            user.role.name != RoleName.ADMIN and days >= get_settings().inactive_account_days
        ),
    )
