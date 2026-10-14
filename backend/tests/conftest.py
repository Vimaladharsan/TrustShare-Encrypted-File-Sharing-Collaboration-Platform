"""Shared test setup. Tests run against the real databases:
docker compose exec backend pytest
"""

import asyncio
import shutil
import uuid
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pymongo import MongoClient
from redis import Redis
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.main import app
from app.models import Role, User

TEST_EMAIL_DOMAIN = "@pytest.example.com"
TEST_PASSWORD = "Str0ng!Passw0rd"


# ---------- database helpers (run outside the app, with their own connections) ----------


async def _test_user_ids() -> list[str]:
    engine = create_async_engine(get_settings().postgres_url)
    try:
        async with async_sessionmaker(engine)() as session:
            result = await session.execute(
                select(User.id).where(User.email.like(f"%{TEST_EMAIL_DOMAIN}"))
            )
            return [str(user_id) for user_id in result.scalars()]
    finally:
        await engine.dispose()


async def _delete_test_users() -> None:
    engine = create_async_engine(get_settings().postgres_url)
    try:
        async with async_sessionmaker(engine)() as session:
            await session.execute(delete(User).where(User.email.like(f"%{TEST_EMAIL_DOMAIN}")))
            await session.commit()
    finally:
        await engine.dispose()


def _delete_test_files(user_ids: list[str]) -> None:
    settings = get_settings()
    mongo = MongoClient(settings.mongo_url)
    try:
        db = mongo[settings.mongo_db]
        db["files"].delete_many({"owner_id": {"$in": user_ids}})
        db["folders"].delete_many({"owner_id": {"$in": user_ids}})
        db["activity_logs"].delete_many({"user_id": {"$in": user_ids}})
    finally:
        mongo.close()
    for user_id in user_ids:
        shutil.rmtree(Path(settings.storage_dir) / user_id, ignore_errors=True)


async def _set_role(email: str, role_name: str) -> None:
    engine = create_async_engine(get_settings().postgres_url)
    try:
        async with async_sessionmaker(engine)() as session:
            role_id = await session.scalar(select(Role.id).where(Role.name == role_name))
            await session.execute(update(User).where(User.email == email).values(role_id=role_id))
            await session.commit()
    finally:
        await engine.dispose()


def set_role(email: str, role_name: str) -> None:
    """Change a test user's role directly in the database (e.g. make a Guest)."""
    asyncio.run(_set_role(email, role_name))


def clear_rate_limits() -> None:
    redis = Redis.from_url(get_settings().redis_url)
    for key in redis.scan_iter("rl:*"):
        redis.delete(key)
    redis.close()


# ---------- fixtures ----------


@pytest.fixture(scope="session")
def client() -> Iterator[TestClient]:
    # Many accounts are created quickly in tests, so raise the per-IP limits
    # (the rate-limit test lowers them again on purpose).
    settings = get_settings()
    settings.login_rate_limit_per_minute = 1000
    settings.register_rate_limit_per_minute = 1000
    settings.forgot_password_rate_limit_per_minute = 1000
    clear_rate_limits()

    # Using TestClient as a context manager runs the app's startup/shutdown (DB connections).
    with TestClient(app) as test_client:
        yield test_client

    # Remove everything the tests created, so the dev databases stay clean.
    _delete_test_files(asyncio.run(_test_user_ids()))
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
