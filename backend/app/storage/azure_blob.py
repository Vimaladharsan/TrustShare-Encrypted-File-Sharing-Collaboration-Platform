"""Object storage in Azure Blob Storage (Milestone 2 – the brief allows AWS S3 or Azure Blob).

Same five operations as S3Storage, so SecureFileStore doesn't care which provider holds the bytes.
The container is private (no anonymous access), and every blob is already AES-256-GCM ciphertext
before it gets here. The Azure SDK is synchronous here, so each call runs in a worker thread.
"""

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from functools import lru_cache
from pathlib import Path
from typing import Any

from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError
from azure.storage.blob import BlobServiceClient, ContentSettings

from app.core.config import get_settings

logger = logging.getLogger(__name__)

READ_CHUNK = 1024 * 1024


class AzureBlobStorage:
    def __init__(self, service: BlobServiceClient, container: str) -> None:
        self.container = service.get_container_client(container)

    async def save(self, key: str, source: Path) -> None:
        """Upload a finished (already encrypted) file; large files go up in blocks."""

        def upload() -> None:
            with source.open("rb") as data:
                self.container.upload_blob(
                    key,
                    data,
                    overwrite=True,
                    # ciphertext, never the "real" type
                    content_settings=ContentSettings(content_type="application/octet-stream"),
                    max_concurrency=4,
                )

        await asyncio.to_thread(upload)

    async def open(self, key: str) -> AsyncIterator[bytes]:
        """Stream a blob back piece by piece."""
        downloader = await asyncio.to_thread(self.container.download_blob, key, max_concurrency=1)
        chunks = downloader.chunks()
        while piece := await asyncio.to_thread(next, chunks, b""):
            yield piece

    async def delete(self, key: str) -> None:
        with contextlib.suppress(ResourceNotFoundError):  # already gone: idempotent, like S3
            await asyncio.to_thread(self.container.delete_blob, key, delete_snapshots="include")

    async def exists(self, key: str) -> bool:
        return await asyncio.to_thread(self.container.get_blob_client(key).exists)

    def ensure_bucket(self) -> None:
        """Create the private container if it doesn't exist yet (called once at startup)."""
        with contextlib.suppress(ResourceExistsError):
            self.container.create_container()  # no public access by default
            logger.info("Created storage container %s", self.container.container_name)

    def ping(self) -> None:
        self.container.get_container_properties()


@lru_cache
def get_azure_storage() -> AzureBlobStorage:
    settings = get_settings()
    service: Any = BlobServiceClient.from_connection_string(
        settings.azure_storage_connection_string.get_secret_value(),
        max_single_get_size=READ_CHUNK,
        max_chunk_get_size=READ_CHUNK,
    )
    return AzureBlobStorage(service, settings.azure_container)
