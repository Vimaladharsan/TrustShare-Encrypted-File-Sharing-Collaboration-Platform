from pymongo import AsyncMongoClient

from app.core.config import Settings

_client: AsyncMongoClient | None = None


def init_mongo(settings: Settings) -> None:
    global _client
    _client = AsyncMongoClient(settings.mongo_url, serverSelectionTimeoutMS=2000)


async def close_mongo() -> None:
    if _client is not None:
        await _client.close()


async def ping_mongo() -> None:
    if _client is None:
        raise RuntimeError("MongoDB is not initialised")
    await _client.admin.command("ping")
