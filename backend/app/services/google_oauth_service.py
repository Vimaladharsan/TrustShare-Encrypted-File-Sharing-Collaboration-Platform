"""Log in with Google – OAuth 2.0 Authorization Code flow with PKCE (OpenID Connect).

1. /google/login  : we create a random `state` (CSRF protection) and a PKCE `code_verifier`,
                    keep them in Redis for 10 minutes and send the browser to Google.
2. Google         : the user signs in and agrees; Google sends the browser back with a `code`.
3. /google/callback: the state must match (used once). We swap the code (+ verifier) for an
                    ID token, check Google's signature, our client id, the issuer, expiry and that
                    Google has verified the email.
4. Account        : already linked → that user; same verified email → link to it; else create a
                    new User. Then a normal session starts – or the MFA step if MFA is on.

Redis key:  oauth_state:{sha256(state)} -> PKCE code_verifier   (10 min, single use)
"""

import asyncio
import base64
import hashlib
import json
import logging
import secrets
import urllib.parse
import urllib.request
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import jwt
from fastapi import Request
from pymongo.asynchronous.database import AsyncDatabase
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.permissions import RoleName
from app.core.rate_limit import client_ip
from app.core.security import hash_token
from app.models import User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import TokenResponse
from app.services.activity_service import ActivityService
from app.services.auth_service import AuthService
from app.services.mfa_service import MfaService

logger = logging.getLogger(__name__)

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"  # noqa: S105 – a public URL, not a secret
GOOGLE_CERTS_URL = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_ISSUERS = ["https://accounts.google.com", "accounts.google.com"]
STATE_TTL = 600  # seconds


def _error(code: str, message: str) -> AppError:
    return AppError(code, message, 400)


@dataclass(frozen=True)
class GoogleIdentity:
    sub: str  # Google's permanent id for this person
    email: str
    name: str


@lru_cache
def _google_keys() -> jwt.PyJWKClient:
    """Google's public signing keys (fetched once, then cached)."""
    return jwt.PyJWKClient(GOOGLE_CERTS_URL)


class GoogleClient:
    """Talks to Google. Tests replace it with a fake (see get_google_client)."""

    def _exchange(self, code: str, code_verifier: str) -> dict[str, Any]:
        settings = get_settings()
        body = urllib.parse.urlencode(
            {
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret.get_secret_value(),
                "redirect_uri": settings.google_redirect_uri,
                "grant_type": "authorization_code",
                "code_verifier": code_verifier,
            }
        ).encode()
        # S310 warns about opening arbitrary URLs; this one is a fixed https address.
        request = urllib.request.Request(GOOGLE_TOKEN_URL, data=body, method="POST")  # noqa: S310
        with urllib.request.urlopen(request, timeout=15) as response:  # noqa: S310
            return json.loads(response.read())

    def _verify(self, id_token: str) -> dict[str, Any]:
        signing_key = _google_keys().get_signing_key_from_jwt(id_token)
        return jwt.decode(
            id_token,
            signing_key.key,
            algorithms=["RS256"],
            audience=get_settings().google_client_id,  # issued for OUR app, not another one
            issuer=GOOGLE_ISSUERS,
        )

    async def identify(self, code: str, code_verifier: str) -> GoogleIdentity:
        try:
            tokens = await asyncio.to_thread(self._exchange, code, code_verifier)
            claims = await asyncio.to_thread(self._verify, tokens["id_token"])
        except Exception as exc:  # network problem, rejected code, bad signature, …
            logger.warning("Google sign-in failed: %r", exc)
            raise _error("GOOGLE_FAILED", "Google sign-in failed. Please try again.") from exc
        if not claims.get("email_verified"):
            raise _error("GOOGLE_EMAIL_UNVERIFIED", "Your Google email address is not verified.")
        email = claims["email"]
        return GoogleIdentity(sub=claims["sub"], email=email, name=claims.get("name") or email)


def get_google_client() -> GoogleClient:
    return GoogleClient()


def _pkce_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


class GoogleOAuthService:
    def __init__(
        self,
        session: AsyncSession,
        redis: Redis,
        db: AsyncDatabase,
        request: Request,
        client: GoogleClient,
    ) -> None:
        self.session = session
        self.redis = redis
        self.users = UserRepository(session)
        self.activity = ActivityService(db)
        self.request = request
        self.client = client

    async def login_url(self) -> str:
        settings = get_settings()
        if not settings.google_enabled:
            raise AppError("GOOGLE_NOT_CONFIGURED", "Google login is not set up.", 503)
        state = secrets.token_urlsafe(32)
        verifier = secrets.token_urlsafe(64)
        await self.redis.set(f"oauth_state:{hash_token(state)}", verifier, ex=STATE_TTL)
        params = {
            "client_id": settings.google_client_id,
            "redirect_uri": settings.google_redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "code_challenge": _pkce_challenge(verifier),
            "code_challenge_method": "S256",
            "prompt": "select_account",
        }
        return f"{GOOGLE_AUTH_URL}?{urllib.parse.urlencode(params)}"

    async def finish(self, code: str, state: str) -> tuple[TokenResponse, str] | tuple[None, str]:
        """Returns (tokens, refresh token) – or (None, MFA challenge id) if MFA is on."""
        verifier = await self.redis.getdel(f"oauth_state:{hash_token(state)}")  # single use
        if verifier is None:
            raise _error("GOOGLE_STATE_INVALID", "This sign-in link expired. Please try again.")

        identity = await self.client.identify(code, verifier)
        user = await self._find_or_create(identity)
        if not user.is_active:
            raise AppError("ACCOUNT_DISABLED", "This account has been disabled.", 403)

        await self.activity.log(
            self.request, user, "auth.oauth_login", details={"provider": "google"}
        )
        if user.mfa_enabled:
            challenge_id, _ = await MfaService(self.session, self.redis).create_challenge(user.id)
            return None, challenge_id
        return await AuthService(self.session, self.redis).start_session(
            user, client_ip(self.request), self.request.headers.get("user-agent", "")
        )

    async def _find_or_create(self, identity: GoogleIdentity) -> User:
        user = await self.users.get_by_oauth("google", identity.sub)
        if user is not None:
            return user

        user = await self.users.get_by_email(identity.email)
        if user is None:
            # New person: a normal User without a password (they always log in with Google).
            settings = get_settings()
            user = User(
                email=identity.email,
                full_name=identity.name[:100],
                password_hash=None,
                role=await self.users.get_role(RoleName.USER),
                is_email_verified=True,  # Google has verified it
                storage_quota_bytes=settings.default_quota_mb * 1024 * 1024,
            )
            await self.users.add(user)
        else:
            # Same verified email as an existing account → link it (Google proved ownership).
            user.is_email_verified = True
        await self.users.link_oauth(user, "google", identity.sub, identity.email)
        await self.session.commit()
        return user
