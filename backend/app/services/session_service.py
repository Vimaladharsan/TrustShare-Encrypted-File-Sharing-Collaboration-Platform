"""Login sessions in Redis: refresh tokens, rotation, reuse detection, logout.

Redis keys (all expire automatically):
    refresh:{hash}            -> session data (user_id, family, ip, user_agent, created_at)
    refresh_used:{hash}       -> user_id of an already-rotated token (for reuse detection)
    refresh_grace:{hash}      -> who rotated it (user, family, ip, user agent), a few seconds
    user_sessions:{user_id}   -> set of the user's active refresh-token hashes
    access_denylist:{jti}     -> access token revoked by logout (until it would expire anyway)
    revoked_before:{user_id}  -> access tokens issued before this time (ms) are invalid (logout-all)
    revoked_sid:{session id}  -> access tokens of a device that was signed out (until they expire)

A "session id" is the refresh-token family: it stays the same for one device across rotations.
"""

import hashlib
import logging
import secrets
import time
import uuid

from redis.asyncio import Redis

from app.core.config import get_settings
from app.core.errors import AppError
from app.services.security_events import record_security_event

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
        self.grace = settings.refresh_reuse_grace_seconds

    async def create(
        self,
        user_id: uuid.UUID,
        ip: str,
        user_agent: str,
        family: str | None = None,
        signed_in_at: str | None = None,
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
                    "created_at": str(int(time.time())),  # = last activity (each refresh)
                    "signed_in_at": signed_in_at or str(int(time.time())),
                },
            )
            pipe.expire(f"refresh:{token_hash}", self.refresh_ttl)
            pipe.sadd(sessions_key, token_hash)
            pipe.expire(sessions_key, self.refresh_ttl)
            await pipe.execute()
        return token

    async def rotate(self, token: str, ip: str, user_agent: str) -> tuple[str, uuid.UUID, str]:
        """Swap a refresh token for a new one. Returns (new token, user id, session id)."""
        token_hash = _hash(token)
        # Read and delete in one atomic step, so a token can only ever be used once.
        async with self.redis.pipeline(transaction=True) as pipe:
            pipe.hgetall(f"refresh:{token_hash}")
            pipe.delete(f"refresh:{token_hash}")
            session, _ = await pipe.execute()

        if not session:
            retry = await self._grace_retry(token_hash, ip, user_agent)
            if retry is not None:
                return retry
            reused_by = await self.redis.get(f"refresh_used:{token_hash}")
            if reused_by:
                # An old token came back: someone has a copy. Log out every device.
                logger.warning("Refresh token reuse detected for user %s", reused_by)
                await self.revoke_all(uuid.UUID(reused_by))
                await record_security_event("token_reuse", ip=ip, details={"user_id": reused_by})
            raise _invalid_session()

        user_id = uuid.UUID(session["user_id"])
        signed_in_at = session.get("signed_in_at", session.get("created_at"))
        await self.redis.set(f"refresh_used:{token_hash}", str(user_id), ex=self.refresh_ttl)
        if self.grace > 0:
            grace_key = f"refresh_grace:{token_hash}"
            await self.redis.hset(
                grace_key,
                mapping={
                    "user_id": str(user_id),
                    "family": session["family"],
                    "ip": ip,
                    "user_agent": user_agent[:200],
                    "signed_in_at": signed_in_at,
                },
            )
            await self.redis.expire(grace_key, self.grace)
        await self.redis.srem(f"user_sessions:{user_id}", token_hash)
        new_token = await self.create(
            user_id,
            ip,
            user_agent,
            family=session["family"],
            signed_in_at=signed_in_at,
        )
        return new_token, user_id, session["family"]

    async def _grace_retry(
        self, token_hash: str, ip: str, user_agent: str
    ) -> tuple[str, uuid.UUID, str] | None:
        """A token rotated a moment ago comes back from the SAME browser (same IP and user
        agent) – e.g. two tabs, or a page reloaded before the new cookie was saved. That is not
        theft, so the browser simply gets a fresh token instead of being logged out everywhere.
        Anything else – another IP or browser, or after the few-second window – stays reuse."""
        grace = await self.redis.hgetall(f"refresh_grace:{token_hash}")
        if not grace or grace["ip"] != ip or grace["user_agent"] != user_agent[:200]:
            return None
        user_id = uuid.UUID(grace["user_id"])
        logger.info("Refresh token retried within the grace window for user %s", user_id)
        token = await self.create(
            user_id, ip, user_agent, family=grace["family"], signed_in_at=grace.get("signed_in_at")
        )
        return token, user_id, grace["family"]

    async def revoke(self, token: str) -> None:
        """Logout of this device."""
        token_hash = _hash(token)
        user_id = await self.redis.hget(f"refresh:{token_hash}", "user_id")
        await self.redis.delete(f"refresh:{token_hash}")
        if user_id:
            await self.redis.srem(f"user_sessions:{user_id}", token_hash)

    # ---------- devices ----------

    async def list_devices(self, user_id: uuid.UUID) -> list[dict[str, str]]:
        """The user's signed-in devices: one entry per session (refresh-token family)."""
        token_hashes = await self.redis.smembers(f"user_sessions:{user_id}")
        devices: dict[str, dict[str, str]] = {}
        for token_hash in token_hashes:
            session = await self.redis.hgetall(f"refresh:{token_hash}")
            if not session:  # expired meanwhile
                await self.redis.srem(f"user_sessions:{user_id}", token_hash)
                continue
            current = devices.get(session["family"])
            # Two tabs may briefly hold two tokens of one family: keep the most recent.
            if current is None or int(session["created_at"]) > int(current["created_at"]):
                devices[session["family"]] = session
        return sorted(devices.values(), key=lambda s: int(s["created_at"]), reverse=True)

    async def revoke_device(self, user_id: uuid.UUID, session_id: str) -> bool:
        """Sign one device out: its refresh tokens go, and its access token stops working now."""
        sessions_key = f"user_sessions:{user_id}"
        found = False
        for token_hash in await self.redis.smembers(sessions_key):
            if await self.redis.hget(f"refresh:{token_hash}", "family") == session_id:
                await self.redis.delete(f"refresh:{token_hash}")
                await self.redis.srem(sessions_key, token_hash)
                found = True
        if found:
            await self.redis.set(f"revoked_sid:{session_id}", "1", ex=self.access_ttl)
        return found

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
        self, user_id: uuid.UUID, jti: str, issued_at_ms: int, session_id: str | None = None
    ) -> bool:
        async with self.redis.pipeline(transaction=False) as pipe:
            pipe.exists(f"access_denylist:{jti}")
            pipe.get(f"revoked_before:{user_id}")
            pipe.exists(f"revoked_sid:{session_id}" if session_id else "revoked_sid:-")
            denied, revoked_before, device_signed_out = await pipe.execute()
        return (
            bool(denied)
            or bool(session_id and device_signed_out)
            or (revoked_before is not None and issued_at_ms < int(revoked_before))
        )
