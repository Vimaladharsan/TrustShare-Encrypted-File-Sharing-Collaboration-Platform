"""Multi-factor authentication with TOTP (Google Authenticator) and one-time backup codes.

TOTP: phone and server share a secret; both compute code = HMAC(secret, current 30-second window)
-> 6 digits. No network is needed between them.

Redis keys:
    mfa_setup:{user_id}              -> secret shown as QR but not yet confirmed (10 minutes)
    totp_used:{user_id}:{code}       -> a code that was already accepted (blocks replay, 90 s)
    mfa_challenge:{hash}             -> user id between "password ok" and "code ok" (5 minutes)
"""

import asyncio
import base64
import hashlib
import secrets
import uuid
from datetime import UTC, datetime

import pyotp
import qrcode
import qrcode.image.svg
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.security import decrypt_secret, encrypt_secret, verify_password
from app.models import User
from app.repositories.user_repository import UserRepository
from app.schemas.mfa import MfaSetupResponse

SETUP_TTL_SECONDS = 10 * 60
BACKUP_CODE_COUNT = 10
BACKUP_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"  # no 0/o, 1/l/i – easy to read and type


def _normalize(code: str) -> str:
    return code.replace(" ", "").replace("-", "").strip().lower()


def _hash_backup_code(code: str) -> str:
    # Backup codes are long random strings (~40 bits each), so a fast hash is enough:
    # unlike passwords they can't be guessed from a dictionary.
    return hashlib.sha256(_normalize(code).encode()).hexdigest()


def _new_backup_code() -> str:
    raw = "".join(secrets.choice(BACKUP_ALPHABET) for _ in range(8))
    return f"{raw[:4]}-{raw[4:]}"


def _qr_data_uri(text: str) -> str:
    image = qrcode.make(text, image_factory=qrcode.image.svg.SvgPathImage)
    return "data:image/svg+xml;base64," + base64.b64encode(image.to_string()).decode()


def _invalid_code() -> AppError:
    return AppError("INVALID_MFA_CODE", "That code is not valid. Please try again.", 400)


class MfaService:
    def __init__(self, session: AsyncSession, redis: Redis) -> None:
        self.session = session
        self.redis = redis
        self.users = UserRepository(session)

    # ---------- turning MFA on ----------

    async def start_setup(self, user: User) -> MfaSetupResponse:
        if user.mfa_enabled:
            raise AppError("MFA_ALREADY_ENABLED", "Two-step verification is already on.", 409)
        secret = pyotp.random_base32()  # 160-bit shared secret
        await self.redis.set(f"mfa_setup:{user.id}", secret, ex=SETUP_TTL_SECONDS)
        uri = pyotp.TOTP(secret).provisioning_uri(
            name=user.email, issuer_name=get_settings().mfa_issuer
        )
        return MfaSetupResponse(
            secret=secret, otpauth_uri=uri, qr_code=_qr_data_uri(uri), expires_in=SETUP_TTL_SECONDS
        )

    async def enable(self, user: User, code: str) -> list[str]:
        """Confirm the setup with a code from the app; returns the one-time backup codes."""
        if user.mfa_enabled:
            raise AppError("MFA_ALREADY_ENABLED", "Two-step verification is already on.", 409)
        secret = await self.redis.get(f"mfa_setup:{user.id}")
        if secret is None:
            raise AppError("MFA_SETUP_EXPIRED", "Setup expired. Please start again.", 400)
        # Proves the phone was set up correctly before MFA is switched on (no lock-out).
        if not await self._accept_totp(user.id, secret, code):
            raise _invalid_code()

        backup_codes = [_new_backup_code() for _ in range(BACKUP_CODE_COUNT)]
        user.mfa_secret_encrypted = encrypt_secret(secret)
        user.mfa_enabled = True
        await self.users.replace_backup_codes(user.id, [_hash_backup_code(c) for c in backup_codes])
        await self.session.commit()
        await self.redis.delete(f"mfa_setup:{user.id}")
        return backup_codes

    async def disable(self, user: User, password: str, code: str) -> None:
        if not user.mfa_enabled:
            raise AppError("MFA_NOT_ENABLED", "Two-step verification is not on.", 400)
        # Turning off a security feature needs both factors again.
        if not await asyncio.to_thread(verify_password, password, user.password_hash):
            raise AppError("INVALID_CREDENTIALS", "Incorrect password.", 401)
        if not await self.verify_code(user, code):
            raise _invalid_code()
        user.mfa_enabled = False
        user.mfa_secret_encrypted = None
        await self.users.delete_backup_codes(user.id)
        await self.session.commit()

    async def regenerate_backup_codes(self, user: User, code: str) -> list[str]:
        """New set of backup codes (the old ones stop working). Needs a current code."""
        if not user.mfa_enabled:
            raise AppError("MFA_NOT_ENABLED", "Two-step verification is not on.", 400)
        if not await self.verify_code(user, code):
            raise _invalid_code()
        backup_codes = [_new_backup_code() for _ in range(BACKUP_CODE_COUNT)]
        await self.users.replace_backup_codes(user.id, [_hash_backup_code(c) for c in backup_codes])
        await self.session.commit()
        return backup_codes

    # ---------- checking a code ----------

    async def verify_code(self, user: User, code: str) -> bool:
        """True for a valid authenticator code or an unused backup code (which is then used up).
        Does not commit – the caller commits."""
        if not user.mfa_enabled or not user.mfa_secret_encrypted:
            return False
        normalized = _normalize(code)
        if normalized.isdigit() and len(normalized) == 6:
            return await self._accept_totp(
                user.id, decrypt_secret(user.mfa_secret_encrypted), normalized
            )
        backup = await self.users.get_unused_backup_code(user.id, _hash_backup_code(normalized))
        if backup is None:
            return False
        backup.used_at = datetime.now(UTC)
        await self.session.flush()
        return True

    async def _accept_totp(self, user_id: uuid.UUID, secret: str, code: str) -> bool:
        code = _normalize(code)
        # valid_window=1 also accepts the previous/next 30 s window (phone clock drift).
        if not pyotp.TOTP(secret).verify(code, valid_window=1):
            return False
        # Each code works once: remember it for longer than it stays valid (3 windows = 90 s).
        first_use = await self.redis.set(f"totp_used:{user_id}:{code}", "1", ex=90, nx=True)
        return bool(first_use)

    # ---------- login challenge (between password and code) ----------

    async def create_challenge(self, user_id: uuid.UUID) -> tuple[str, int]:
        challenge_id = secrets.token_urlsafe(24)
        ttl = get_settings().mfa_challenge_minutes * 60
        await self.redis.set(
            f"mfa_challenge:{hashlib.sha256(challenge_id.encode()).hexdigest()}",
            str(user_id),
            ex=ttl,
        )
        return challenge_id, ttl

    async def user_for_challenge(self, challenge_id: str) -> uuid.UUID | None:
        key = f"mfa_challenge:{hashlib.sha256(challenge_id.encode()).hexdigest()}"
        value = await self.redis.get(key)
        return uuid.UUID(value) if value else None

    async def finish_challenge(self, challenge_id: str) -> None:
        await self.redis.delete(
            f"mfa_challenge:{hashlib.sha256(challenge_id.encode()).hexdigest()}"
        )

    async def remaining_backup_codes(self, user: User) -> int:
        return await self.users.count_unused_backup_codes(user.id)
