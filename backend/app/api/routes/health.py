import asyncio
import logging
from collections.abc import Awaitable, Callable

from fastapi import APIRouter, Response, status

from app.db.mongo import ping_mongo
from app.db.postgres import ping_postgres
from app.db.redis import ping_redis

router = APIRouter(tags=["health"])
logger = logging.getLogger(__name__)


async def check(name: str, ping: Callable[[], Awaitable[None]]) -> str:
    try:
        await asyncio.wait_for(ping(), timeout=2)
        return "ok"
    except Exception as exc:
        logger.warning("Health check failed for %s: %r", name, exc)
        return "error"


@router.get("/health", summary="Status of PostgreSQL, MongoDB and Redis")
async def health(response: Response) -> dict:
    """Checks the three databases in parallel. Returns 503 if any is down."""
    postgres, mongodb, redis = await asyncio.gather(
        check("postgres", ping_postgres),
        check("mongodb", ping_mongo),
        check("redis", ping_redis),
    )
    services = {"postgres": postgres, "mongodb": mongodb, "redis": redis}
    healthy = all(result == "ok" for result in services.values())
    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "ok" if healthy else "degraded", "services": services}
