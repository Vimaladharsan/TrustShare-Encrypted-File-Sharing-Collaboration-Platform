from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response, status
from pymongo.asynchronous.database import AsyncDatabase
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_token_payload
from app.api.routes.auth import clear_refresh_cookie, set_refresh_cookie
from app.core.config import get_settings
from app.db.mongo import get_mongo
from app.db.postgres import get_db
from app.db.redis import get_redis
from app.models import User
from app.schemas.auth import ChangePasswordRequest, TokenResponse
from app.schemas.mfa import (
    MfaCodeRequest,
    MfaDisableRequest,
    MfaEnableResponse,
    MfaSetupResponse,
    MfaStatusResponse,
)
from app.schemas.user import DeleteAccountRequest, DeviceSessionList, ProfileUpdate, UserResponse
from app.services.account_service import AccountService
from app.services.activity_service import ActivityService
from app.services.email_service import EmailSender, account_deleted_email, get_email_sender
from app.services.mfa_service import MfaService
from app.storage.secure_store import SecureFileStore, get_file_store

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserResponse, summary="The logged-in user's profile")
async def read_me(user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse.from_user(user)


@router.patch("/me", response_model=UserResponse, summary="Update my profile (display name)")
async def update_me(
    data: ProfileUpdate,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    db: AsyncDatabase = Depends(get_mongo),
) -> UserResponse:
    updated = await AccountService(session, redis, db, request).update_profile(user, data.full_name)
    return UserResponse.from_user(updated)


@router.delete(
    "/me",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete my account and all my files (password, 2-step code if on, typed confirmation)",
)
async def delete_me(
    data: DeleteAccountRequest,
    request: Request,
    response: Response,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    db: AsyncDatabase = Depends(get_mongo),
    storage: SecureFileStore = Depends(get_file_store),
    sender: EmailSender = Depends(get_email_sender),
) -> None:
    result = await AccountService(session, redis, db, request).delete_account(
        user, data, storage, db
    )
    clear_refresh_cookie(response)
    background_tasks.add_task(
        sender.send,
        account_deleted_email(
            result["email"], result["name"], result["files_deleted"], get_settings().frontend_url
        ),
    )


# ---------- signed-in devices ----------


@router.get("/me/sessions", response_model=DeviceSessionList, summary="My signed-in devices")
async def my_devices(
    request: Request,
    user: User = Depends(get_current_user),
    payload: dict[str, Any] = Depends(get_token_payload),
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    db: AsyncDatabase = Depends(get_mongo),
) -> DeviceSessionList:
    service = AccountService(session, redis, db, request)
    return DeviceSessionList(items=await service.devices(user, payload.get("sid")))


@router.delete(
    "/me/sessions/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Sign one device out (its access stops immediately)",
)
async def sign_out_device(
    session_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    db: AsyncDatabase = Depends(get_mongo),
) -> None:
    await AccountService(session, redis, db, request).sign_out_device(user, session_id)


@router.post(
    "/me/password",
    response_model=TokenResponse,
    summary="Change my password (logs out every other device; this one gets a new session)",
)
async def change_password(
    data: ChangePasswordRequest,
    request: Request,
    response: Response,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    db: AsyncDatabase = Depends(get_mongo),
) -> TokenResponse:
    service = AccountService(session, redis, db, request)
    tokens, refresh_token = await service.change_password(
        user, data.current_password, data.new_password
    )
    set_refresh_cookie(response, refresh_token)
    return tokens


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


@router.post(
    "/me/mfa/backup-codes",
    response_model=MfaEnableResponse,
    summary="Replace my backup codes (needs a current code; the old codes stop working)",
)
async def regenerate_backup_codes(
    data: MfaCodeRequest,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    db: AsyncDatabase = Depends(get_mongo),
) -> MfaEnableResponse:
    codes = await MfaService(session, redis).regenerate_backup_codes(user, data.code)
    await ActivityService(db).log(
        request, user, "auth.backup_codes_regenerated", resource_type="user"
    )
    return MfaEnableResponse(backup_codes=codes)
