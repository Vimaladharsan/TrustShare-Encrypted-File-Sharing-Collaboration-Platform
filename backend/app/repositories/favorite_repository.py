"""MongoDB access for starred files (collection "favorites"). Reads and writes only – no rules."""

from datetime import UTC, datetime

from pymongo.asynchronous.database import AsyncDatabase


class FavoriteRepository:
    def __init__(self, db: AsyncDatabase) -> None:
        self.favorites = db["favorites"]

    async def add(self, user_id: str, file_id: str) -> None:
        # Upsert: starring twice is harmless (unique index on user_id + file_id).
        await self.favorites.update_one(
            {"user_id": user_id, "file_id": file_id},
            {"$setOnInsert": {"created_at": datetime.now(UTC)}},
            upsert=True,
        )

    async def remove(self, user_id: str, file_id: str) -> None:
        await self.favorites.delete_one({"user_id": user_id, "file_id": file_id})

    async def file_ids(self, user_id: str, among: list[str] | None = None) -> list[str]:
        """The user's starred file ids (optionally only those in `among`), newest first."""
        query: dict = {"user_id": user_id}
        if among is not None:
            query["file_id"] = {"$in": among}
        cursor = self.favorites.find(query, {"file_id": 1}).sort("created_at", -1)
        return [row["file_id"] for row in await cursor.to_list(length=None)]

    async def delete_for_user(self, user_id: str) -> None:
        await self.favorites.delete_many({"user_id": user_id})
