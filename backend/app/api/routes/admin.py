from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_permission
from app.core.permissions import Perm
from app.db.postgres import get_db
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserListResponse, UserResponse

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get(
    "/users",
    response_model=UserListResponse,
    summary="List all users (requires user:read – admins only)",
    dependencies=[Depends(require_permission(Perm.USER_READ))],
)
async def list_users(
    search: str | None = Query(None, max_length=100, description="Match email or name"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
) -> UserListResponse:
    users, total = await UserRepository(session).list_users(search, limit, offset)
    return UserListResponse(items=[UserResponse.from_user(u) for u in users], total=total)
