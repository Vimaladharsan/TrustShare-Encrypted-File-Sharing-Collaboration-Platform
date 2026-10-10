import asyncio
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response, status

from app.core.config import get_settings
from app.db.mongo import close_mongo, init_mongo, ping_mongo
from app.db.postgres import close_postgres, init_postgres, ping_postgres
from app.db.redis import close_redis, init_redis, ping_redis

logger = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Open database connections on startup, close them on shutdown."""
    settings = get_settings()
    init_postgres(settings)
    init_mongo(settings)
    init_redis(settings)
    yield
    await close_redis()
    await close_mongo()
    await close_postgres()


app = FastAPI(title="TrustShare API", version="0.1.0", lifespan=lifespan)


async def check(name: str, ping: Callable[[], Awaitable[None]]) -> str:
    try:
        await asyncio.wait_for(ping(), timeout=2)
        return "ok"
    except Exception as exc:
        logger.warning("Health check failed for %s: %r", name, exc)
        return "error"


@app.get("/api/health")
async def health(response: Response) -> dict:
    """Checks PostgreSQL, MongoDB and Redis in parallel. Returns 503 if any is down."""
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
