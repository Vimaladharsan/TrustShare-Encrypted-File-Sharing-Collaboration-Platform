"""Shared test setup. Tests run against the real databases:
docker compose exec backend pytest
"""

import asyncio
import uuid
from collections.abc import Callable, Iterator

import pytest
from fastapi.testclient import TestClient
from redis import Redis
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


def clear_rate_limits() -> None:
    redis = Redis.from_url(get_settings().redis_url)
    for key in redis.scan_iter("rl:*"):
        redis.delete(key)
    redis.close()


@pytest.fixture(scope="session")
def client() -> Iterator[TestClient]:
    # Many accounts are created quickly in tests, so raise the per-IP limits
    # (the rate-limit test lowers them again on purpose).
    settings = get_settings()
    settings.login_rate_limit_per_minute = 1000
    settings.register_rate_limit_per_minute = 1000
    clear_rate_limits()

    # Using TestClient as a context manager runs the app's startup/shutdown (DB connections).
    with TestClient(app) as test_client:
        yield test_client
    # Remove every account the tests created, so the dev database stays clean.
    asyncio.run(_delete_test_users())
    clear_rate_limits()


@pytest.fixture(autouse=True)
def fresh_cookies(client: TestClient) -> None:
    """Each test starts with no cookies, so one test's login can't leak into another."""
    client.cookies.clear()


@pytest.fixture
def new_email() -> Callable[[], str]:
    """Returns a function producing a unique test email each call."""
    return lambda: f"user-{uuid.uuid4().hex[:10]}{TEST_EMAIL_DOMAIN}"
