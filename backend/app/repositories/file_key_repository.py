"""Database access for wrapped file keys (PostgreSQL file_keys). No business rules here."""

import uuid
from collections.abc import Collection, Sequence
from datetime import UTC, datetime

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FileKey
from app.services.encryption_service import ALGORITHM, EncryptedKey


class FileKeyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, file_id: str, owner_id: uuid.UUID, key: EncryptedKey) -> None:
        self.session.add(
            FileKey(
                file_id=file_id,
                owner_id=owner_id,
                wrapped_key=key.wrapped_key,
                key_version=key.key_version,
                algorithm=ALGORITHM,
            )
        )
        await self.session.flush()

    async def get(self, file_id: str) -> EncryptedKey | None:
        row = await self.session.get(FileKey, file_id)
        return EncryptedKey(row.wrapped_key, row.key_version) if row else None

    async def delete(self, file_id: str) -> None:
        await self.session.execute(delete(FileKey).where(FileKey.file_id == file_id))

    # ---------- key rotation ----------

    async def older_than(
        self,
        version: int,
        limit: int,
        owner_id: uuid.UUID | None = None,
        skip: Collection[str] = (),
    ) -> Sequence[FileKey]:
        """Keys not yet wrapped with master key `version` (optionally one owner's only)."""
        query = select(FileKey).where(FileKey.key_version != version)
        if owner_id is not None:
            query = query.where(FileKey.owner_id == owner_id)
        if skip:
            query = query.where(FileKey.file_id.not_in(skip))
        result = await self.session.execute(query.order_by(FileKey.file_id).limit(limit))
        return result.scalars().all()

    async def replace(self, row: FileKey, key: EncryptedKey) -> None:
        row.wrapped_key, row.key_version = key.wrapped_key, key.key_version
        row.rotated_at = datetime.now(UTC)

    async def count_by_version(self) -> dict[int, int]:
        result = await self.session.execute(
            select(FileKey.key_version, func.count()).group_by(FileKey.key_version)
        )
        return {version: count for version, count in result.all()}
