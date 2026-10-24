"""Which object storage holds the encrypted files: STORAGE_PROVIDER=s3 (RustFS / AWS S3, default)
or STORAGE_PROVIDER=azure (Azure Blob Storage). Both offer the same operations, so the rest of the
backend – encryption, keys, sharing – is identical for either provider."""

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Protocol


class ObjectStorage(Protocol):
    async def save(self, key: str, source: Path) -> None: ...

    def open(self, key: str) -> AsyncIterator[bytes]: ...

    async def delete(self, key: str) -> None: ...

    async def exists(self, key: str) -> bool: ...

    def ensure_bucket(self) -> None: ...

    def ping(self) -> None: ...


def get_object_storage() -> ObjectStorage:
    from app.core.config import get_settings

    if get_settings().storage_provider == "azure":
        from app.storage.azure_blob import get_azure_storage

        return get_azure_storage()
    from app.storage.s3 import get_s3_storage

    return get_s3_storage()
