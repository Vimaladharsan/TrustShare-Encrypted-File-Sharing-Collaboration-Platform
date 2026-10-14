"""Login sessions in Redis: refresh tokens, rotation, reuse detection, logout.

Redis keys (all expire automatically):
    refresh:{hash}            -> session data (user_id, family, ip, user_agent, created_at)
    refresh_used:{hash}       -> user_id of an already-rotated token (for reuse detection)
    user_sessions:{user_id}   -> set of the user's active refresh-token hashes
    access_denylist:{jti}     -> access token revoked by logout (until it would expire anyway)
    revoked_before:{user_id}  -> access tokens issued before this time (ms) are invalid (logout-all)
"""

import hashlib
import logging
import secrets
import time
import uuid

from redis.asyncio import Redis

from app.core.config import get_settings
from app.core.errors import AppError

logger = logging.getLogger(__name__)


def _hash(token: str) -> str:
    # Only the hash is stored, so a Redis leak doesn't reveal usable tokens.
    return hashlib.sha256(token.encode()).hexdigest()


def _invalid_session() -> AppError:
    return AppError("INVALID_SESSION", "Your session has expired. Please log in again.", 401)


class SessionService:
    def __init__(self, redis: Redis) -> None:
        self.redis = redis
        settings = get_settings()
        self.refresh_ttl = settings.refresh_token_ttl_days * 24 * 3600
        self.access_ttl = settings.access_token_ttl_minutes * 60

    async def create(
        self, user_id: uuid.UUID, ip: str, user_agent: str, family: str | None = None
    ) -> str:
        """Start a session; returns the raw refresh token (only ever sent to the browser)."""
        token = secrets.token_urlsafe(32)  # 256 bits of randomness
        token_hash = _hash(token)
        sessions_key = f"user_sessions:{user_id}"
        async with self.redis.pipeline(transaction=True) as pipe:
            pipe.hset(
                f"refresh:{token_hash}",
                mapping={
                    "user_id": str(user_id),
                    "family": family or uuid.uuid4().hex,
                    "ip": ip,
                    "user_agent": user_agent[:200],
                    "created_at": str(int(time.time())),
                },
            )
            pipe.expire(f"refresh:{token_hash}", self.refresh_ttl)
            pipe.sadd(sessions_key, token_hash)
            pipe.expire(sessions_key, self.refresh_ttl)
            await pipe.execute()
        return token

    async def rotate(self, token: str, ip: str, user_agent: str) -> tuple[str, uuid.UUID]:
        """Swap a refresh token for a new one. Returns (new token, user id)."""
        token_hash = _hash(token)
        # Read and delete in one atomic step, so a token can only ever be used once.
        async with self.redis.pipeline(transaction=True) as pipe:
            pipe.hgetall(f"refresh:{token_hash}")
            pipe.delete(f"refresh:{token_hash}")
            session, _ = await pipe.execute()

        if not session:
            reused_by = await self.redis.get(f"refresh_used:{token_hash}")
            if reused_by:
                # An old token came back: someone has a copy. Log out every device.
                logger.warning("Refresh token reuse detected for user %s", reused_by)
                await self.revoke_all(uuid.UUID(reused_by))
            raise _invalid_session()

        user_id = uuid.UUID(session["user_id"])
        await self.redis.set(f"refresh_used:{token_hash}", str(user_id), ex=self.refresh_ttl)
        await self.redis.srem(f"user_sessions:{user_id}", token_hash)
        new_token = await self.create(user_id, ip, user_agent, family=session["family"])
        return new_token, user_id

    async def revoke(self, token: str) -> None:
        """Logout of this device."""
        token_hash = _hash(token)
        user_id = await self.redis.hget(f"refresh:{token_hash}", "user_id")
        await self.redis.delete(f"refresh:{token_hash}")
        if user_id:
            await self.redis.srem(f"user_sessions:{user_id}", token_hash)

    async def revoke_all(self, user_id: uuid.UUID) -> None:
        """Logout of every device: delete all refresh tokens and invalidate access tokens."""
        sessions_key = f"user_sessions:{user_id}"
        token_hashes = await self.redis.smembers(sessions_key)
        async with self.redis.pipeline(transaction=True) as pipe:
            for token_hash in token_hashes:
                pipe.delete(f"refresh:{token_hash}")
            pipe.delete(sessions_key)
            # Access tokens issued before this moment stop working (they last at most access_ttl).
            # Milliseconds, so a token issued earlier in the same second is caught too.
            pipe.set(f"revoked_before:{user_id}", str(int(time.time() * 1000)), ex=self.access_ttl)
            await pipe.execute()

    async def deny_access_token(self, jti: str, expires_at: int) -> None:
        """Block one access token until its natural expiry."""
        remaining = expires_at - int(time.time())
        if remaining > 0:
            await self.redis.set(f"access_denylist:{jti}", "1", ex=remaining)

    async def is_access_token_revoked(
        self, user_id: uuid.UUID, jti: str, issued_at_ms: int
    ) -> bool:
        async with self.redis.pipeline(transaction=False) as pipe:
            pipe.exists(f"access_denylist:{jti}")
            pipe.get(f"revoked_before:{user_id}")
            denied, revoked_before = await pipe.execute()
        return bool(denied) or (revoked_before is not None and issued_at_ms < int(revoked_before))
