from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.core.config import Settings

_engine: AsyncEngine | None = None


def init_postgres(settings: Settings) -> None:
    global _engine
    # pool_pre_ping: test a pooled connection before using it (survives DB restarts)
    _engine = create_async_engine(settings.postgres_url, pool_pre_ping=True)


async def close_postgres() -> None:
    if _engine is not None:
        await _engine.dispose()


async def ping_postgres() -> None:
    if _engine is None:
        raise RuntimeError("PostgreSQL is not initialised")
    async with _engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
