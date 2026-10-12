from redis.asyncio import Redis

from app.core.config import Settings

_redis: Redis | None = None


def init_redis(settings: Settings) -> None:
    global _redis
    _redis = Redis.from_url(settings.redis_url, decode_responses=True)


async def close_redis() -> None:
    if _redis is not None:
        await _redis.aclose()


def get_redis() -> Redis:
    """FastAPI dependency returning the shared Redis client (it pools connections itself)."""
    if _redis is None:
        raise RuntimeError("Redis is not initialised")
    return _redis


async def ping_redis() -> None:
    await get_redis().ping()
