import uuid

from fastapi import APIRouter, Depends, Query, Request
from pymongo.asynchronous.database import AsyncDatabase
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_permission
from app.core.permissions import Perm
from app.db.mongo import get_mongo
from app.db.postgres import get_db
from app.db.redis import get_redis
from app.models import User
from app.schemas.user import AdminUserListResponse, AdminUserResponse, AdminUserUpdate
from app.services.admin_service import AdminService

router = APIRouter(prefix="/admin", tags=["admin"])

can_read_users = require_permission(Perm.USER_READ)
can_manage_users = require_permission(Perm.USER_MANAGE)


def admin_service(
    request: Request,
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    db: AsyncDatabase = Depends(get_mongo),
) -> AdminService:
    return AdminService(session, redis, db, request)


@router.get(
    "/users",
    response_model=AdminUserListResponse,
    summary="List all users (requires user:read – admins only)",
    dependencies=[Depends(can_read_users)],
)
async def list_users(
    search: str | None = Query(None, max_length=100, description="Match email or name"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    service: AdminService = Depends(admin_service),
) -> AdminUserListResponse:
    items, total = await service.list_users(search, limit, offset)
    return AdminUserListResponse(items=items, total=total)


@router.patch(
    "/users/{user_id}",
    response_model=AdminUserResponse,
    summary="Change a user's role and/or enable or disable the account (requires user:manage)",
)
async def update_user(
    user_id: uuid.UUID,
    data: AdminUserUpdate,
    admin: User = Depends(can_manage_users),
    service: AdminService = Depends(admin_service),
) -> AdminUserResponse:
    return await service.update_user(admin, user_id, data)


@router.post(
    "/users/{user_id}/unlock",
    response_model=AdminUserResponse,
    summary="Unlock an account locked after too many failed logins (requires user:manage)",
)
async def unlock_user(
    user_id: uuid.UUID,
    admin: User = Depends(can_manage_users),
    service: AdminService = Depends(admin_service),
) -> AdminUserResponse:
    return await service.unlock(admin, user_id)
