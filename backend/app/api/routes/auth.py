import contextlib
from typing import Any
from urllib.parse import urlencode

import jwt
from fastapi import APIRouter, BackgroundTasks, Cookie, Depends, Request, Response, status
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPAuthorizationCredentials
from pymongo.asynchronous.database import AsyncDatabase
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import bearer_scheme, get_current_user, get_token_payload
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.rate_limit import client_ip, rate_limit
from app.core.security import decode_access_token
from app.db.mongo import get_mongo
from app.db.postgres import get_db
from app.db.redis import get_redis
from app.models import User
from app.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    VerifyEmailRequest,
)
from app.schemas.mfa import MfaRequiredResponse, MfaVerifyRequest
from app.schemas.user import UserResponse
from app.services.auth_service import AuthService
from app.services.email_service import EmailSender, get_email_sender
from app.services.email_verification_service import EmailVerificationService
from app.services.google_oauth_service import (
    GoogleClient,
    GoogleOAuthService,
    get_google_client,
)
from app.services.password_reset_service import PasswordResetService
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
    request: Request,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    db: AsyncDatabase = Depends(get_mongo),
    sender: EmailSender = Depends(get_email_sender),
) -> UserResponse:
    user = await AuthService(session, redis).register(data)
    email = await EmailVerificationService(session, redis, db, request).create_email(user)
    background_tasks.add_task(sender.send, email)  # "Verify your email", sent after the reply
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


# ---------- forgot / reset password ----------


def reset_service(
    request: Request,
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    db: AsyncDatabase = Depends(get_mongo),
) -> PasswordResetService:
    return PasswordResetService(session, redis, db, request)


@router.post(
    "/forgot-password",
    response_model=MessageResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Email a password reset link (same answer whether or not the account exists)",
    dependencies=[Depends(rate_limit("forgot", "forgot_password_rate_limit_per_minute"))],
)
async def forgot_password(
    data: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    service: PasswordResetService = Depends(reset_service),
    sender: EmailSender = Depends(get_email_sender),
) -> MessageResponse:
    email = await service.request_reset(data.email)
    if email:
        background_tasks.add_task(sender.send, email)  # sent after the response goes out
    return MessageResponse(
        message="If an account exists for this email, we've sent a link to reset the password."
    )


@router.post(
    "/reset-password",
    response_model=MessageResponse,
    summary="Choose a new password using the link from the email (logs out every device)",
    dependencies=[Depends(rate_limit("forgot", "forgot_password_rate_limit_per_minute"))],
)
async def reset_password(
    data: ResetPasswordRequest,
    service: PasswordResetService = Depends(reset_service),
) -> MessageResponse:
    await service.reset(data.token, data.new_password)
    return MessageResponse(message="Your password has been changed. Please log in.")


# ---------- email verification ----------


@router.post(
    "/verify-email",
    response_model=MessageResponse,
    summary="Confirm the email address with the link from the sign-up email",
    dependencies=[Depends(rate_limit("forgot", "forgot_password_rate_limit_per_minute"))],
)
async def verify_email(
    data: VerifyEmailRequest,
    request: Request,
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    db: AsyncDatabase = Depends(get_mongo),
) -> MessageResponse:
    await EmailVerificationService(session, redis, db, request).verify(data.token)
    return MessageResponse(message="Your email is verified.")


@router.post(
    "/verify-email/resend",
    response_model=MessageResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Send a new verification email to the logged-in user",
    dependencies=[Depends(rate_limit("forgot", "forgot_password_rate_limit_per_minute"))],
)
async def resend_verification(
    request: Request,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    db: AsyncDatabase = Depends(get_mongo),
    sender: EmailSender = Depends(get_email_sender),
) -> MessageResponse:
    email = await EmailVerificationService(session, redis, db, request).resend(user)
    background_tasks.add_task(sender.send, email)
    return MessageResponse(message=f"We've sent a new verification link to {user.email}.")


# ---------- Google login ----------


@router.get("/providers", summary="Which extra login methods are available (for the login page)")
async def providers() -> dict[str, bool]:
    return {"google": get_settings().google_enabled}


def google_service(
    request: Request,
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    db: AsyncDatabase = Depends(get_mongo),
    client: GoogleClient = Depends(get_google_client),
) -> GoogleOAuthService:
    return GoogleOAuthService(session, redis, db, request, client)


def _to_frontend(path: str, **query: str) -> RedirectResponse:
    url = f"{get_settings().frontend_url}{path}"
    if query:
        url += "?" + urlencode(query)
    return RedirectResponse(url, status_code=status.HTTP_302_FOUND)


@router.get(
    "/google/login",
    summary="Start Google login (redirects to Google)",
    dependencies=[Depends(rate_limit("login", "login_rate_limit_per_minute"))],
)
async def google_login(service: GoogleOAuthService = Depends(google_service)) -> RedirectResponse:
    try:
        return RedirectResponse(await service.login_url(), status_code=status.HTTP_302_FOUND)
    except AppError as exc:
        return _to_frontend("/login", oauth_error=exc.message)


@router.get("/google/callback", summary="Google sends the user back here after signing in")
async def google_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    service: GoogleOAuthService = Depends(google_service),
) -> RedirectResponse:
    """Always ends in a redirect to our frontend – logged in, at the MFA step, or with a message."""
    if error or not code or not state:  # e.g. the user pressed "Cancel" on Google's page
        return _to_frontend("/login", oauth_error="Google sign-in was cancelled.")
    try:
        tokens, value = await service.finish(code, state)
    except AppError as exc:
        return _to_frontend("/login", oauth_error=exc.message)

    if tokens is None:  # MFA is on: the login page asks for the 6-digit code next
        return _to_frontend("/login", mfa_challenge=value)
    response = _to_frontend("/auth/google")  # frontend then calls /auth/refresh with the cookie
    set_refresh_cookie(response, value)
    return response
