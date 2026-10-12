import contextlib
from typing import Any

import jwt
from fastapi import APIRouter, Cookie, Depends, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import bearer_scheme, get_current_user, get_token_payload
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.rate_limit import client_ip, rate_limit
from app.core.security import decode_access_token
from app.db.postgres import get_db
from app.db.redis import get_redis
from app.models import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse
from app.schemas.mfa import MfaRequiredResponse, MfaVerifyRequest
from app.schemas.user import UserResponse
from app.services.auth_service import AuthService
from app.services.session_service import SessionService

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE = "refresh_token"
REFRESH_COOKIE_PATH = "/api/auth"  # the browser sends the cookie only to auth endpoints


def set_refresh_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        REFRESH_COOKIE,
        token,
        max_age=settings.refresh_token_ttl_days * 24 * 3600,
        httponly=True,  # JavaScript can never read it (protects against XSS theft)
        secure=settings.cookie_secure,  # HTTPS-only in production
        samesite="strict",  # never sent by other websites (protects against CSRF)
        path=REFRESH_COOKIE_PATH,
    )


def clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(REFRESH_COOKIE, path=REFRESH_COOKIE_PATH)


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new account (role: user)",
    dependencies=[Depends(rate_limit("register", "register_rate_limit_per_minute"))],
)
async def register(
    data: RegisterRequest,
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> UserResponse:
    user = await AuthService(session, redis).register(data)
    return UserResponse.from_user(user)


@router.post(
    "/login",
    response_model=TokenResponse | MfaRequiredResponse,
    summary="Log in: returns tokens, or an MFA challenge if two-step verification is on",
    dependencies=[Depends(rate_limit("login", "login_rate_limit_per_minute"))],
)
async def login(
    data: LoginRequest,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> TokenResponse | MfaRequiredResponse:
    result, refresh_token = await AuthService(session, redis).login(
        data, client_ip(request), request.headers.get("user-agent", "")
    )
    if refresh_token:  # no cookie until the second factor is passed
        set_refresh_cookie(response, refresh_token)
    return result


@router.post(
    "/mfa/verify",
    response_model=TokenResponse,
    summary="Second login step: submit the 6-digit code (or a backup code)",
    dependencies=[Depends(rate_limit("login", "login_rate_limit_per_minute"))],
)
async def verify_mfa(
    data: MfaVerifyRequest,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> TokenResponse:
    tokens, refresh_token = await AuthService(session, redis).verify_mfa(
        data, client_ip(request), request.headers.get("user-agent", "")
    )
    set_refresh_cookie(response, refresh_token)
    return tokens


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Swap the refresh-token cookie for a new access token (and a new cookie)",
)
async def refresh(
    request: Request,
    response: Response,
    refresh_token: str | None = Cookie(None, alias=REFRESH_COOKIE),
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> TokenResponse:
    if not refresh_token:
        raise AppError("INVALID_SESSION", "Your session has expired. Please log in again.", 401)
    tokens, new_refresh_token = await AuthService(session, redis).refresh(
        refresh_token, client_ip(request), request.headers.get("user-agent", "")
    )
    set_refresh_cookie(response, new_refresh_token)
    return tokens


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Log out of this device",
)
async def logout(
    response: Response,
    refresh_token: str | None = Cookie(None, alias=REFRESH_COOKIE),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    redis: Redis = Depends(get_redis),
) -> None:
    sessions = SessionService(redis)
    if refresh_token:
        await sessions.revoke(refresh_token)
    if credentials:
        # Also block the current access token for the rest of its 15 minutes.
        with contextlib.suppress(jwt.InvalidTokenError):
            payload = decode_access_token(credentials.credentials)
            await sessions.deny_access_token(payload["jti"], payload["exp"])
    clear_refresh_cookie(response)


@router.post(
    "/logout-all",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Log out of every device",
)
async def logout_all(
    response: Response,
    user: User = Depends(get_current_user),
    payload: dict[str, Any] = Depends(get_token_payload),
    redis: Redis = Depends(get_redis),
) -> None:
    sessions = SessionService(redis)
    await sessions.revoke_all(user.id)
    await sessions.deny_access_token(payload["jti"], payload["exp"])
    clear_refresh_cookie(response)
