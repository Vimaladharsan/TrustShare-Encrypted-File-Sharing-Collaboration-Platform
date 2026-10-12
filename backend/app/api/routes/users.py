from fastapi import APIRouter, Depends, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.postgres import get_db
from app.db.redis import get_redis
from app.models import User
from app.schemas.mfa import (
    MfaCodeRequest,
    MfaDisableRequest,
    MfaEnableResponse,
    MfaSetupResponse,
    MfaStatusResponse,
)
from app.schemas.user import UserResponse
from app.services.mfa_service import MfaService

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserResponse, summary="The logged-in user's profile")
async def read_me(user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse.from_user(user)


# ---------- two-step verification (MFA) ----------


@router.get("/me/mfa", response_model=MfaStatusResponse, summary="Is two-step verification on?")
async def mfa_status(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> MfaStatusResponse:
    remaining = await MfaService(session, redis).remaining_backup_codes(user)
    return MfaStatusResponse(enabled=user.mfa_enabled, backup_codes_remaining=remaining)


@router.post(
    "/me/mfa/setup",
    response_model=MfaSetupResponse,
    summary="Step 1: get a QR code to scan with Google Authenticator",
)
async def mfa_setup(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> MfaSetupResponse:
    return await MfaService(session, redis).start_setup(user)


@router.post(
    "/me/mfa/enable",
    response_model=MfaEnableResponse,
    summary="Step 2: confirm with a code from the app; returns one-time backup codes",
)
async def mfa_enable(
    data: MfaCodeRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> MfaEnableResponse:
    codes = await MfaService(session, redis).enable(user, data.code)
    return MfaEnableResponse(backup_codes=codes)


@router.post(
    "/me/mfa/disable",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Turn off two-step verification (needs password and a code)",
)
async def mfa_disable(
    data: MfaDisableRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> None:
    await MfaService(session, redis).disable(user, data.password, data.code)
