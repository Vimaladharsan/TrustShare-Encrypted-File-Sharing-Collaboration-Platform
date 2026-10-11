from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.models import User
from app.schemas.user import UserResponse

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserResponse, summary="The logged-in user's profile")
async def read_me(user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse.from_user(user)
