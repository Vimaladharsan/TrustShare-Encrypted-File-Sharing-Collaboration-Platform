"""Account lockout after repeated wrong passwords (protects one account from guessing).

Redis keys:
    login_fail:{user_id}  -> number of consecutive failures (expires after the lockout window)
    lockout:{user_id}     -> present while the account is locked
"""

import math
import uuid

from redis.asyncio import Redis

from app.core.config import get_settings
from app.core.errors import AppError


class LoginGuard:
    def __init__(self, redis: Redis) -> None:
        self.redis = redis
        settings = get_settings()
        self.max_failures = settings.max_failed_logins
        self.window = settings.lockout_minutes * 60

    async def ensure_not_locked(self, user_id: uuid.UUID) -> None:
        seconds_left = await self.redis.ttl(f"lockout:{user_id}")
        if seconds_left > 0:
            minutes = math.ceil(seconds_left / 60)
            raise AppError(
                "ACCOUNT_LOCKED",
                f"Too many failed attempts. Try again in {minutes} minute(s).",
                status_code=429,
                headers={"Retry-After": str(seconds_left)},
            )

    async def record_failure(self, user_id: uuid.UUID) -> None:
        key = f"login_fail:{user_id}"
        failures = await self.redis.incr(key)
        if failures == 1:
            await self.redis.expire(key, self.window)
        if failures >= self.max_failures:
            await self.redis.set(f"lockout:{user_id}", "1", ex=self.window)
            await self.redis.delete(key)

    async def clear(self, user_id: uuid.UUID) -> None:
        await self.redis.delete(f"login_fail:{user_id}")

    async def unlock(self, user_id: uuid.UUID) -> None:
        """Used by an admin to unlock an account early."""
        await self.redis.delete(f"lockout:{user_id}", f"login_fail:{user_id}")
