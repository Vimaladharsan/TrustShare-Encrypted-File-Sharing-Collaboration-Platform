"""TrustShare API – application entry point. Interactive docs: http://localhost:8000/docs"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import setup_logging
from app.core.middleware import register_middleware
from app.db.mongo import close_mongo, init_mongo
from app.db.postgres import close_postgres, init_postgres
from app.db.redis import close_redis, init_redis

setup_logging(get_settings().log_level)
logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Open database connections on startup, close them on shutdown."""
    settings = get_settings()
    init_postgres(settings)
    init_mongo(settings)
    init_redis(settings)
    logger.info("%s API started", settings.app_name)
    yield
    await close_redis()
    await close_mongo()
    await close_postgres()


app = FastAPI(title="TrustShare API", version="0.1.0", lifespan=lifespan)
register_middleware(app)
register_exception_handlers(app)
app.include_router(api_router)
