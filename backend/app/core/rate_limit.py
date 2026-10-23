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
    """The visitor's IP. Behind Caddy / the Vite proxy, Uvicorn's --proxy-headers has already
    replaced the proxy's address with the one from X-Forwarded-For (trusted proxies only)."""
    if not request.client:
        return "unknown"
    host = request.client.host
    # "::ffff:172.18.0.1" is the IPv4 address 172.18.0.1 written as IPv6 – count it as one.
    return host.removeprefix("::ffff:")


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
            if count == limit + 1:  # one event per IP and minute, not one per request
                from app.services.security_events import record_security_event

                await record_security_event(
                    "blocked_request",
                    request=request,
                    message="Rate limit exceeded",
                    details={"scope": scope, "limit_per_minute": limit},
                )
            raise AppError(
                "RATE_LIMITED",
                "Too many requests. Please wait a minute and try again.",
                status_code=429,
                headers={"Retry-After": str(60 - now % 60)},
            )

    return limiter
