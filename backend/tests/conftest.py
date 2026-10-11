"""Shared test setup. Tests run against the real databases:
docker compose exec backend pytest
"""

import asyncio
import uuid
from collections.abc import Callable, Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.main import app
from app.models import User

TEST_EMAIL_DOMAIN = "@pytest.example.com"
TEST_PASSWORD = "Str0ng!Passw0rd"


async def _delete_test_users() -> None:
    engine = create_async_engine(get_settings().postgres_url)
    try:
        async with async_sessionmaker(engine)() as session:
            await session.execute(delete(User).where(User.email.like(f"%{TEST_EMAIL_DOMAIN}")))
            await session.commit()
    finally:
        await engine.dispose()


@pytest.fixture(scope="session")
def client() -> Iterator[TestClient]:
    # Using TestClient as a context manager runs the app's startup/shutdown (DB connections).
    with TestClient(app) as test_client:
        yield test_client
    # Remove every account the tests created, so the dev database stays clean.
    asyncio.run(_delete_test_users())


@pytest.fixture
def new_email() -> Callable[[], str]:
    """Returns a function producing a unique test email each call."""
    return lambda: f"user-{uuid.uuid4().hex[:10]}{TEST_EMAIL_DOMAIN}"
