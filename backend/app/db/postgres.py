from collections.abc import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def init_postgres(settings: Settings) -> None:
    global _engine, _sessionmaker
    # pool_pre_ping: test a pooled connection before using it (survives DB restarts)
    _engine = create_async_engine(settings.postgres_url, pool_pre_ping=True)
    # expire_on_commit=False: objects stay usable after commit (needed with async sessions)
    _sessionmaker = async_sessionmaker(_engine, expire_on_commit=False)


async def close_postgres() -> None:
    if _engine is not None:
        await _engine.dispose()


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: one database session per request, closed automatically afterwards."""
    if _sessionmaker is None:
        raise RuntimeError("PostgreSQL is not initialised")
    async with _sessionmaker() as session:
        yield session


async def ping_postgres() -> None:
    if _engine is None:
        raise RuntimeError("PostgreSQL is not initialised")
    async with _engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
