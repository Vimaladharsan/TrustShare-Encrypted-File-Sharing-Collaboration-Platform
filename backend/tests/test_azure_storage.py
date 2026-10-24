"""Azure Blob Storage (STORAGE_PROVIDER=azure) – tested against Azurite, Microsoft's official
Azure Storage emulator. Skipped unless AZURE_TEST_CONNECTION_STRING points to one (CI starts it).

    docker run -d --name azurite-test --network trustshare_default \\
        mcr.microsoft.com/azure-storage/azurite:3.35.0 azurite-blob --blobHost 0.0.0.0 \\
        --skipApiVersionCheck --loose
"""

import asyncio
import os
import uuid
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from azure.storage.blob import BlobServiceClient
from bson import ObjectId
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.core.config import get_settings
from app.storage.azure_blob import AzureBlobStorage, get_azure_storage
from tests.test_files import PDF, auth, mongo_db, new_user, upload

CONNECTION = os.environ.get("AZURE_TEST_CONNECTION_STRING", "")
pytestmark = pytest.mark.skipif(not CONNECTION, reason="no Azurite emulator configured")
CONTAINER = "trustshare-test"


def container_client():
    return BlobServiceClient.from_connection_string(CONNECTION).get_container_client(CONTAINER)


@pytest.fixture
def storage() -> AzureBlobStorage:
    store = AzureBlobStorage(BlobServiceClient.from_connection_string(CONNECTION), CONTAINER)
    store.ensure_bucket()
    return store


@pytest.fixture
def azure_provider() -> Iterator[None]:
    """Switch the running app to Azure for one test, then back to S3."""
    settings = get_settings()
    old = (
        settings.storage_provider,
        settings.azure_storage_connection_string,
        settings.azure_container,
    )
    settings.storage_provider = "azure"
    settings.azure_storage_connection_string = SecretStr(CONNECTION)
    settings.azure_container = CONTAINER
    get_azure_storage.cache_clear()
    get_azure_storage().ensure_bucket()
    try:
        yield
    finally:
        (
            settings.storage_provider,
            settings.azure_storage_connection_string,
            settings.azure_container,
        ) = old
        get_azure_storage.cache_clear()


async def _read(storage: AzureBlobStorage, key: str) -> bytes:
    return b"".join([piece async for piece in storage.open(key)])


def test_blob_round_trip(storage: AzureBlobStorage, tmp_path: Path) -> None:
    key = f"test/{uuid.uuid4()}"
    data = os.urandom(3 * 1024 * 1024 + 123)  # several 1 MiB pieces
    source = tmp_path / "object.enc"
    source.write_bytes(data)

    asyncio.run(storage.save(key, source))

    assert asyncio.run(storage.exists(key)) is True
    assert asyncio.run(_read(storage, key)) == data
    asyncio.run(storage.delete(key))
    assert asyncio.run(storage.exists(key)) is False
    asyncio.run(storage.delete(key))  # deleting twice is harmless
    storage.ensure_bucket()  # creating the container twice is harmless too
    storage.ping()


def test_container_is_private(storage: AzureBlobStorage) -> None:
    properties = container_client().get_container_properties()

    assert properties.public_access is None  # no anonymous read access


def test_encrypted_files_live_in_azure(
    client: TestClient, new_email: Callable[[], str], azure_provider: None
) -> None:
    token = new_user(client, new_email())
    file_id = upload(client, token, "Project_Report.pdf", PDF).json()["id"]
    doc = mongo_db()["files"].find_one({"_id": ObjectId(file_id)})

    stored = container_client().download_blob(doc["storage_key"]).readall()
    download = client.get(f"/api/files/{file_id}/download", headers=auth(token))
    health = client.get("/api/health").json()["services"]["storage"]
    client.delete(f"/api/files/{file_id}", headers=auth(token))

    assert doc["storage_backend"] == "azure"
    assert stored.startswith(b"TSE1") and b"TrustShare test file" not in stored  # ciphertext
    assert download.status_code == 200 and download.content == PDF  # decrypted for the owner
    assert health == "ok"
    assert not container_client().get_blob_client(doc["storage_key"]).exists()  # deleted
