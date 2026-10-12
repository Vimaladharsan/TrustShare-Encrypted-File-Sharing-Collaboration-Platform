"""Per-IP rate limiting with Redis counters (protects the whole system from bots).

Fixed one-minute windows: key rl:{scope}:{ip}:{minute} counts requests and expires after 60 s.
"""

import time
from collections.abc import Awaitable, Callable

from fastapi import Depends, Request
from redis.asyncio import Redis

from app.core.config import get_settings
from app.core.errors import AppError
from app.db.redis import get_redis


def client_ip(request: Request) -> str:
    # In production behind a reverse proxy, Uvicorn's --proxy-headers sets the real client IP.
    return request.client.host if request.client else "unknown"


def rate_limit(scope: str, limit_setting: str) -> Callable[..., Awaitable[None]]:
    """Route dependency: allow at most `settings.<limit_setting>` requests per minute per IP."""

    async def limiter(request: Request, redis: Redis = Depends(get_redis)) -> None:
        limit = getattr(get_settings(), limit_setting)
        now = int(time.time())
        key = f"rl:{scope}:{client_ip(request)}:{now // 60}"
        count = await redis.incr(key)
        if count == 1:
            await redis.expire(key, 60)
        if count > limit:
            raise AppError(
                "RATE_LIMITED",
                "Too many requests. Please wait a minute and try again.",
                status_code=429,
                headers={"Retry-After": str(60 - now % 60)},
            )

    return limiter
