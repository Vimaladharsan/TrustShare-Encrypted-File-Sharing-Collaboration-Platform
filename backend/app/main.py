"""TrustShare API – application entry point. Interactive docs: http://localhost:8000/docs"""

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from app.activity_monitoring.service import register_hook
from app.api.router import api_router
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import setup_logging
from app.core.middleware import register_middleware
from app.db.mongo import close_mongo, ensure_indexes, init_mongo
from app.db.postgres import close_postgres, init_postgres
from app.db.redis import close_redis, init_redis
from app.notifications.scheduler import loop as notification_scheduler
from app.notifications.service import bind_app
from app.notifications.triggers import on_activity, on_security_event
from app.security_monitoring.detection import evaluate
from app.services.security_events import register_event_hook
from app.storage.objects import get_object_storage

setup_logging(get_settings().log_level)
logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Open database connections on startup, close them on shutdown."""
    settings = get_settings()
    init_postgres(settings)
    init_mongo(settings)
    init_redis(settings)
    await ensure_indexes()
    await asyncio.to_thread(Path(settings.storage_dir).mkdir, parents=True, exist_ok=True)
    await _ensure_bucket()
    logger.info("%s API started", settings.app_name)
    scheduler = (
        asyncio.create_task(notification_scheduler()) if settings.scheduler_enabled else None
    )
    yield
    if scheduler is not None:
        scheduler.cancel()
    await close_redis()
    await close_mongo()
    await close_postgres()


async def _ensure_bucket() -> None:
    """Create the private storage bucket if needed. RustFS may still be starting, so retry."""
    for attempt in range(1, 11):
        try:
            await asyncio.to_thread(get_object_storage().ensure_bucket)
            return
        except Exception as exc:  # connection refused while RustFS boots
            logger.warning("Object storage not ready (attempt %d/10): %s", attempt, exc)
            await asyncio.sleep(2)
    logger.error("Object storage unavailable – uploads and downloads will fail until it is up")


app = FastAPI(title="TrustShare API", version="0.1.0", lifespan=lifespan)
register_middleware(app)
register_exception_handlers(app)
app.include_router(api_router)

# Milestone 3: after every recorded activity – suspicious-activity rules, then notifications;
# after every security event – alerts to admins and to the affected user.
register_hook(evaluate)
register_hook(on_activity)
register_event_hook(on_security_event)
bind_app(app)
