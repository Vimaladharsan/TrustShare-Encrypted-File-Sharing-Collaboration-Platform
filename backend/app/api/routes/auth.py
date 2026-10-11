from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.postgres import get_db
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse
from app.schemas.user import UserResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new account (role: user)",
)
async def register(data: RegisterRequest, session: AsyncSession = Depends(get_db)) -> UserResponse:
    user = await AuthService(session).register(data)
    return UserResponse.from_user(user)


@router.post("/login", response_model=TokenResponse, summary="Log in and receive an access token")
async def login(data: LoginRequest, session: AsyncSession = Depends(get_db)) -> TokenResponse:
    return await AuthService(session).login(data)
