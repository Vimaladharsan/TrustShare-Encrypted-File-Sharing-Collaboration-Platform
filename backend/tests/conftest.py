"""Shared test setup. Tests run against the real databases:
docker compose exec backend pytest
"""

import asyncio
import re
import shutil
import uuid
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pymongo import MongoClient
from redis import Redis
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.main import app
from app.models import FileKey, Role, User
from app.services.email_service import Email, get_email_sender
from app.storage.s3 import get_s3_client

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
        # Failed logins for made-up test emails have no user id – match them by email.
        test_email = {"$regex": f"{re.escape(TEST_EMAIL_DOMAIN)}$"}
        db["activity_logs"].delete_many({"details.email": test_email})
        # Logs of test accounts that a test deleted (their ids are gone from PostgreSQL).
        db["activity_logs"].delete_many({"actor_email": test_email})
    finally:
        mongo.close()
    for user_id in user_ids:
        shutil.rmtree(Path(settings.storage_dir) / user_id, ignore_errors=True)
        _delete_objects(f"{user_id}/")


def _delete_objects(prefix: str) -> None:
    """Remove a test user's encrypted objects from the bucket (RustFS)."""
    s3, bucket = get_s3_client(), get_settings().s3_bucket
    listed = s3.list_objects_v2(Bucket=bucket, Prefix=prefix).get("Contents", [])
    if listed:
        s3.delete_objects(
            Bucket=bucket, Delete={"Objects": [{"Key": obj["Key"]} for obj in listed]}
        )


# ---------- helpers for storage / key tests ----------


def stored_object(storage_key: str) -> bytes | None:
    """The raw object exactly as stored in the bucket (None if it doesn't exist)."""
    s3 = get_s3_client()
    try:
        return s3.get_object(Bucket=get_settings().s3_bucket, Key=storage_key)["Body"].read()
    except s3.exceptions.NoSuchKey:
        return None


def put_object(storage_key: str, data: bytes) -> None:
    """Overwrite a stored object – used to simulate tampering."""
    get_s3_client().put_object(Bucket=get_settings().s3_bucket, Key=storage_key, Body=data)


async def _file_key(file_id: str) -> FileKey | None:
    engine = create_async_engine(get_settings().postgres_url)
    try:
        async with async_sessionmaker(engine)() as session:
            return await session.get(FileKey, file_id)
    finally:
        await engine.dispose()


def file_key_row(file_id: str) -> FileKey | None:
    """The PostgreSQL file_keys row for a file (wrapped key), or None."""
    return asyncio.run(_file_key(file_id))


async def _drop_file_key(file_id: str) -> None:
    engine = create_async_engine(get_settings().postgres_url)
    try:
        async with async_sessionmaker(engine)() as session:
            await session.execute(delete(FileKey).where(FileKey.file_id == file_id))
            await session.commit()
    finally:
        await engine.dispose()


def drop_file_key(file_id: str) -> None:
    asyncio.run(_drop_file_key(file_id))


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


async def _set_last_login(email: str, days_ago: int) -> None:
    engine = create_async_engine(get_settings().postgres_url)
    try:
        async with async_sessionmaker(engine)() as session:
            when = datetime.now(UTC) - timedelta(days=days_ago)
            await session.execute(
                update(User).where(User.email == email).values(last_login_at=when)
            )
            await session.commit()
    finally:
        await engine.dispose()


def set_last_login(email: str, days_ago: int) -> None:
    """Pretend a test user last logged in `days_ago` days ago (for the inactivity rule)."""
    asyncio.run(_set_last_login(email, days_ago))


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


class FakeSender:
    """Collects emails instead of sending them (tests must never send real email)."""

    def __init__(self) -> None:
        self.sent: list[Email] = []

    def send(self, email: Email) -> None:
        self.sent.append(email)

    def links(self, path: str) -> list[Email]:
        """Only the emails whose link goes to this page, e.g. "reset-password"."""
        return [email for email in self.sent if f"/{path}?token=" in email.text]


@pytest.fixture(autouse=True)
def outbox() -> Iterator[FakeSender]:
    """Every test gets a fresh fake email sender."""
    sender = FakeSender()
    app.dependency_overrides[get_email_sender] = lambda: sender
    yield sender
    app.dependency_overrides.pop(get_email_sender, None)


@pytest.fixture(autouse=True)
def fresh_cookies(client: TestClient) -> None:
    """Each test starts with no cookies, so one test's login can't leak into another."""
    client.cookies.clear()


@pytest.fixture
def new_email() -> Callable[[], str]:
    """Returns a function producing a unique test email each call."""
    return lambda: f"user-{uuid.uuid4().hex[:10]}{TEST_EMAIL_DOMAIN}"
