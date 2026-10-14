"""User management by admins: change roles, enable/disable accounts, unlock lockouts.

Safety rules:
  - admins can't change their own role or disable themselves (no accidental self-lockout)
  - the last active admin can never be removed, so the system always has someone in charge
  - disabling an account logs it out of every device immediately
Every change is written to the activity log.
"""

import uuid

from fastapi import Request
from pymongo.asynchronous.database import AsyncDatabase
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.permissions import RoleName
from app.models import User
from app.repositories.user_repository import UserRepository
from app.schemas.user import AdminUserResponse, AdminUserUpdate, UserResponse
from app.services.activity_service import ActivityService
from app.services.login_guard import LoginGuard
from app.services.session_service import SessionService


def _not_found() -> AppError:
    return AppError("USER_NOT_FOUND", "User not found.", 404)


class AdminService:
    def __init__(
        self, session: AsyncSession, redis: Redis, db: AsyncDatabase, request: Request
    ) -> None:
        self.session = session
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
        return await self._response(user)

    async def _response(self, user: User) -> AdminUserResponse:
        locked = await self.guard.locked_ids([user.id])
        return _to_response(user, user.id in locked)


def _to_response(user: User, is_locked: bool) -> AdminUserResponse:
    return AdminUserResponse(**UserResponse.from_user(user).model_dump(), is_locked=is_locked)
