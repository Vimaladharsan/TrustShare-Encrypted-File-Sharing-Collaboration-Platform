"""MongoDB connection (PyMongo async client) and indexes.

Collections (docs/database.md §2):
    files          – metadata of every uploaded file
    activity_logs  – append-only audit trail
"""

from pymongo import ASCENDING, DESCENDING, AsyncMongoClient, IndexModel
from pymongo.asynchronous.database import AsyncDatabase

from app.core.config import Settings

_client: AsyncMongoClient | None = None
_db: AsyncDatabase | None = None

# Indexes = lookup shortcuts for the queries the app actually runs.
INDEXES: dict[str, list[IndexModel]] = {
    "files": [
        # Listing a user's files in a folder, sorted by name (the most common query).
        IndexModel(
            [
                ("owner_id", ASCENDING),
                ("folder_id", ASCENDING),
                ("status", ASCENDING),
                ("name_lower", ASCENDING),
            ],
            name="owner_folder_status_name",
        ),
        # "Recent" view and sorting by date.
        IndexModel(
            [("owner_id", ASCENDING), ("status", ASCENDING), ("created_at", DESCENDING)],
            name="owner_status_created",
        ),
        # Duplicate detection.
        IndexModel([("owner_id", ASCENDING), ("sha256", ASCENDING)], name="owner_sha256"),
    ],
    "activity_logs": [
        IndexModel([("user_id", ASCENDING), ("created_at", DESCENDING)], name="user_created"),
        IndexModel([("action", ASCENDING), ("created_at", DESCENDING)], name="action_created"),
    ],
}


def init_mongo(settings: Settings) -> None:
    global _client, _db
    _client = AsyncMongoClient(settings.mongo_url, serverSelectionTimeoutMS=2000, tz_aware=True)
    _db = _client[settings.mongo_db]


async def ensure_indexes() -> None:
    """Create the indexes if they don't exist yet (safe to run on every start)."""
    db = get_mongo()
    for collection, indexes in INDEXES.items():
        await db[collection].create_indexes(indexes)


async def close_mongo() -> None:
    if _client is not None:
        await _client.close()


def get_mongo() -> AsyncDatabase:
    """FastAPI dependency returning the TrustShare database."""
    if _db is None:
        raise RuntimeError("MongoDB is not initialised")
    return _db


async def ping_mongo() -> None:
    if _client is None:
        raise RuntimeError("MongoDB is not initialised")
    await _client.admin.command("ping")
