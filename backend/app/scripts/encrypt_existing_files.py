"""Encrypt files uploaded before Milestone 2 and move them into the private bucket.

    docker compose exec backend python -m app.scripts.encrypt_existing_files

Milestone 1 stored files as plaintext on the server's disk (`encryption: null`). For each such file
this script: encrypts it with a new AES-256-GCM key, uploads the ciphertext to object storage,
stores the wrapped key in PostgreSQL, updates the metadata, and deletes the plaintext copy.

Safe to run more than once: already-encrypted files are skipped. Files whose plaintext is missing
on disk are reported and left untouched.
"""

import asyncio
import uuid
from datetime import UTC, datetime

from pymongo.asynchronous.database import AsyncDatabase
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.db.mongo import close_mongo, get_mongo, init_mongo
from app.storage.local import get_storage
from app.storage.objects import get_object_storage
from app.storage.secure_store import SecureFileStore

PLAINTEXT = {"$or": [{"encryption": None}, {"encryption": {"$exists": False}}]}


async def encrypt_existing(
    db: AsyncDatabase, store: SecureFileStore, owner_id: str | None = None
) -> dict[str, int]:
    """Convert every plaintext file (optionally only one owner's). Returns converted / missing."""
    counts = {"converted": 0, "missing": 0}
    query = {**PLAINTEXT, **({"owner_id": owner_id} if owner_id else {})}
    async for doc in db["files"].find(query):
        plain_path = store.legacy.path(doc["storage_key"])
        if not await asyncio.to_thread(plain_path.exists):
            counts["missing"] += 1
            print(f"  ! {doc['original_name']} ({doc['_id']}): plaintext missing – skipped")
            continue
        stored = await store.store(str(doc["_id"]), uuid.UUID(doc["owner_id"]), plain_path)
        await db["files"].update_one(
            {"_id": doc["_id"]}, {"$set": {**stored, "updated_at": datetime.now(UTC)}}
        )
        await store.legacy.delete(doc["storage_key"])  # the plaintext copy is gone for good
        counts["converted"] += 1
        print(f"  ✓ {doc['original_name']} ({doc['_id']}) encrypted")
    return counts


async def main() -> None:
    settings = get_settings()
    init_mongo(settings)
    engine = create_async_engine(settings.postgres_url)
    try:
        await asyncio.to_thread(get_object_storage().ensure_bucket)
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            store = SecureFileStore(session, get_object_storage(), get_storage())
            counts = await encrypt_existing(get_mongo(), store)
    finally:
        await engine.dispose()
        await close_mongo()
    print(f"Done: {counts['converted']} file(s) encrypted, {counts['missing']} missing.")


if __name__ == "__main__":
    asyncio.run(main())
