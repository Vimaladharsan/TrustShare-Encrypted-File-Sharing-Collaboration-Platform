"""Remove throwaway accounts (e.g. created by the Postman collection) with all their data.

    docker compose exec backend python -m app.scripts.remove_test_accounts postman.example.com

Only domains under example.com (reserved for testing, RFC 2606) are accepted, so a real user can
never be removed by mistake. For each account: encrypted objects and keys, file metadata, folders,
favorites, shares, sessions, its activity logs and security events, then the account itself.
"""

import argparse
import asyncio
import re

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.db.mongo import close_mongo, get_mongo, init_mongo
from app.models import User
from app.repositories.user_repository import UserRepository
from app.services.session_service import SessionService
from app.storage.local import get_storage
from app.storage.objects import get_object_storage
from app.storage.secure_store import SecureFileStore


async def remove(domain: str) -> int:
    settings = get_settings()
    init_mongo(settings)
    db = get_mongo()
    engine = create_async_engine(settings.postgres_url)
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            users = (
                (await session.execute(select(User).where(User.email.like(f"%@{domain}"))))
                .scalars()
                .all()
            )
            store = SecureFileStore(session, get_object_storage(), get_storage())
            for user in users:
                owner, email = str(user.id), user.email
                for doc in await db["files"].find({"owner_id": owner}).to_list(length=None):
                    await store.delete(doc)  # object + key + shares
                await db["files"].delete_many({"owner_id": owner})
                await db["folders"].delete_many({"owner_id": owner})
                await db["favorites"].delete_many({"user_id": owner})
                await db["activity_logs"].delete_many(
                    {"$or": [{"user_id": owner}, {"details.owner_id": owner}]}
                )
                await db["security_events"].delete_many(
                    {"$or": [{"user_id": owner}, {"actor_email": email}]}
                )
                await SessionService(redis).revoke_all(user.id)
                await UserRepository(session).delete(user.id)
                await session.commit()
                print(f"  removed {email}")
            return len(users)
    finally:
        await engine.dispose()
        await redis.aclose()
        await close_mongo()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("domain", help="e.g. postman.example.com")
    domain = parser.parse_args().domain.lower().lstrip("@")
    if not re.fullmatch(r"([a-z0-9-]+\.)*example\.com", domain):
        raise SystemExit("Only test domains under example.com can be removed.")
    print(f"Done: {asyncio.run(remove(domain))} account(s) removed.")


if __name__ == "__main__":
    main()
