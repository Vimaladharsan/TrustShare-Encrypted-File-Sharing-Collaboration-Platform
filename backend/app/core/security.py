"""Password hashing (bcrypt) and access tokens (JWT)."""

import contextlib
import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Any

import bcrypt
import jwt
from cryptography.fernet import Fernet

from app.core.config import get_settings

# Cost factor 12 = 2^12 rounds: ~0.25 s per hash. Slow for attackers, unnoticeable for users.
BCRYPT_ROUNDS = 12


def new_url_token() -> str:
    """Random token for links in emails (256 bits – impossible to guess)."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Only this hash is stored, so a database or Redis leak doesn't reveal usable links."""
    return hashlib.sha256(token.encode()).hexdigest()


def hash_password(password: str) -> str:
    """One-way hash with a random salt. The original password can never be recovered."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(BCRYPT_ROUNDS)).decode()


def verify_password(password: str, password_hash: str | None) -> bool:
    """Hash the typed password with the stored salt and compare (constant-time)."""
    if not password_hash:
        # Account without a password (e.g. Google-only): still spend the same time.
        _dummy_check(password)
        return False
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ValueError:  # bcrypt rejects passwords longer than 72 bytes
        return False


@lru_cache
def _dummy_hash() -> bytes:
    return bcrypt.hashpw(b"dummy-password", bcrypt.gensalt(BCRYPT_ROUNDS))


def _dummy_check(password: str) -> None:
    with contextlib.suppress(ValueError):
        bcrypt.checkpw(password.encode(), _dummy_hash())


def spend_password_check_time(password: str) -> None:
    """Called when the email doesn't exist, so the response takes as long as a real check.
    Otherwise an attacker could tell which emails are registered by timing the reply."""
    _dummy_check(password)


def create_access_token(
    user_id: uuid.UUID, role: str, session_id: str | None = None
) -> tuple[str, int]:
    """Signed JWT proving who the user is. Returns (token, lifetime in seconds).
    `session_id` names the device session it belongs to, so signing that device out also
    stops its access token at once, and the Devices list can mark "this device"."""
    settings = get_settings()
    now = datetime.now(UTC)
    lifetime = timedelta(minutes=settings.access_token_ttl_minutes)
    payload = {
        "sub": str(user_id),  # subject: who this token belongs to
        "role": role,
        "type": "access",
        "jti": uuid.uuid4().hex,  # unique token id (used to revoke it on logout in Phase 3B)
        "iat": now,  # issued at (whole seconds, as the JWT standard defines it)
        # Same moment in milliseconds: "log out everywhere" and password changes block tokens
        # issued before them – whole seconds would let a token from the same second through.
        "iat_ms": int(now.timestamp() * 1000),
        "exp": now + lifetime,  # expires at
    }
    if session_id:
        payload["sid"] = session_id
    token = jwt.encode(
        payload, settings.jwt_secret.get_secret_value(), algorithm=settings.jwt_algorithm
    )
    return token, int(lifetime.total_seconds())


def issued_at_ms(payload: dict[str, Any]) -> int:
    """When a token was issued, in milliseconds (older tokens only have whole seconds)."""
    return int(payload.get("iat_ms", payload["iat"] * 1000))


def decode_access_token(token: str) -> dict[str, Any]:
    """Verify the signature and expiry. Raises jwt.InvalidTokenError if anything is wrong."""
    settings = get_settings()
    payload = jwt.decode(
        token,
        settings.jwt_secret.get_secret_value(),
        algorithms=[settings.jwt_algorithm],  # never let the token choose its own algorithm
        options={"require": ["sub", "exp", "iat", "type"]},
    )
    if payload["type"] != "access":
        raise jwt.InvalidTokenError("Not an access token")
    return payload


# ---------- encryption of stored secrets (MFA) ----------


def _fernet() -> Fernet:
    return Fernet(get_settings().mfa_encryption_key.get_secret_value())


def encrypt_secret(value: str) -> str:
    """Two-way encryption (AES-128 + HMAC via Fernet). Unlike a password hash, the server must be
    able to read the TOTP secret back to compute codes, so it is encrypted rather than hashed."""
    return _fernet().encrypt(value.encode()).decode()


def decrypt_secret(token: str) -> str:
    return _fernet().decrypt(token.encode()).decode()
