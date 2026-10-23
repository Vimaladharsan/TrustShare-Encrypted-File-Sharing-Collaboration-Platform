"""Encrypted storage end to end (Milestone 2, Phases 3–4).

Upload → encrypted object in the private bucket + wrapped key in PostgreSQL → authorized download
decrypts and verifies → tampering rejected."""

import asyncio
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from bson import ObjectId
from fastapi.testclient import TestClient
from pymongo import AsyncMongoClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.scripts.encrypt_existing_files import encrypt_existing
from app.storage.local import get_storage
from app.storage.s3 import get_s3_storage
from app.storage.secure_store import SecureFileStore
from tests.conftest import drop_file_key, file_key_row, put_object, stored_object
from tests.test_files import PDF, auth, mongo_db, new_user, upload

REPORT = b"%PDF-1.4\n" + b"Project_Report confidential numbers 42 " * 200 + b"\n%%EOF\n"


def metadata(file_id: str) -> dict:
    return mongo_db()["files"].find_one({"_id": ObjectId(file_id)})


def test_stored_object_is_unreadable_without_the_backend(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    token = new_user(client, new_email())
    file_id = upload(client, token, "Project_Report.pdf", REPORT).json()["id"]
    doc = metadata(file_id)

    raw = stored_object(doc["storage_key"])  # what someone with the bucket would get

    assert raw is not None
    assert b"Project_Report" not in raw and b"confidential" not in raw
    assert len(raw) > len(REPORT)  # header + a 16-byte tag per chunk
    assert doc["storage_backend"] == "s3"
    assert doc["encryption"]["encrypted_size"] == len(raw)


def test_authorized_download_returns_the_original(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    token = new_user(client, new_email())
    file_id = upload(client, token, "Project_Report.pdf", REPORT).json()["id"]

    download = client.get(f"/api/files/{file_id}/download", headers=auth(token))
    preview = client.get(f"/api/files/{file_id}/preview", headers=auth(token))

    assert download.status_code == 200 and download.content == REPORT
    assert preview.status_code == 200 and preview.content == REPORT


def test_other_user_cannot_download_by_knowing_the_id(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    owner = new_user(client, new_email())
    file_id = upload(client, owner, "private.pdf", PDF).json()["id"]
    stranger = new_user(client, new_email())

    response = client.get(f"/api/files/{file_id}/download", headers=auth(stranger))

    assert response.status_code == 404
    assert PDF not in response.content


def test_every_file_gets_its_own_key(client: TestClient, new_email: Callable[[], str]) -> None:
    token = new_user(client, new_email())
    first = upload(client, token, "a.pdf", PDF).json()["id"]
    second = upload(client, token, "b.pdf", PDF, allow_duplicate="true").json()["id"]

    key_a, key_b = file_key_row(first), file_key_row(second)

    assert key_a.wrapped_key != key_b.wrapped_key
    assert key_a.key_version == get_settings().active_master_key_version
    assert stored_object(metadata(first)["storage_key"]) != stored_object(
        metadata(second)["storage_key"]
    )


def test_tampered_object_is_rejected(client: TestClient, new_email: Callable[[], str]) -> None:
    token = new_user(client, new_email())
    file_id = upload(client, token, "Project_Report.pdf", REPORT).json()["id"]
    key = metadata(file_id)["storage_key"]
    raw = bytearray(stored_object(key))
    raw[40] ^= 0xFF  # an attacker changes one byte in the bucket
    put_object(key, bytes(raw))

    response = client.get(f"/api/files/{file_id}/download", headers=auth(token))

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "FILE_INTEGRITY_ERROR"
    assert b"Project_Report" not in response.content


def test_missing_key_means_no_access(client: TestClient, new_email: Callable[[], str]) -> None:
    token = new_user(client, new_email())
    file_id = upload(client, token, "keyless.pdf", PDF).json()["id"]
    drop_file_key(file_id)

    response = client.get(f"/api/files/{file_id}/download", headers=auth(token))

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "FILE_INTEGRITY_ERROR"


def test_api_never_returns_key_material(client: TestClient, new_email: Callable[[], str]) -> None:
    token = new_user(client, new_email())
    body = upload(client, token, "a.pdf", PDF).json()
    info = client.get(f"/api/files/{body['id']}", headers=auth(token)).json()
    listing = client.get("/api/files", headers=auth(token)).json()

    for payload in (body, info, listing):
        text = str(payload).lower()
        assert "wrapped" not in text and "storage_key" not in text and "key_version" not in text


def test_existing_plaintext_files_are_migrated(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    """A Milestone 1 file (plaintext on disk, encryption null) is encrypted by the script."""
    token = new_user(client, new_email())
    owner_id = client.get("/api/users/me", headers=auth(token)).json()["id"]
    legacy_key = f"{owner_id}/{uuid.uuid4()}"
    plain = get_storage().path(legacy_key)
    plain.parent.mkdir(parents=True, exist_ok=True)
    plain.write_bytes(PDF)
    now = datetime.now(UTC)
    file_id = mongo_db()["files"].insert_one({
        "owner_id": owner_id, "folder_id": None, "original_name": "old.pdf",
        "name_lower": "old.pdf", "extension": "pdf", "mime_type": "application/pdf",
        "category": "document", "size_bytes": len(PDF), "sha256": "x" * 64,
        "storage_backend": "local", "storage_key": legacy_key, "version": 1,
        "status": "active", "trashed_at": None, "encryption": None,
        "created_at": now, "updated_at": now,
    }).inserted_id  # fmt: skip
    # Before migration the old file still downloads (plaintext path).
    before = client.get(f"/api/files/{file_id}/download", headers=auth(token))
    assert before.content == PDF

    counts = asyncio.run(_run_migration(owner_id))  # only this test user's files

    assert counts == {"converted": 1, "missing": 0}
    doc = metadata(str(file_id))
    assert doc["encryption"]["algorithm"] == "AES-256-GCM"
    assert not Path(plain).exists()  # plaintext copy deleted
    assert PDF not in stored_object(doc["storage_key"])
    after = client.get(f"/api/files/{file_id}/download", headers=auth(token))
    assert after.status_code == 200 and after.content == PDF


async def _run_migration(owner_id: str) -> dict[str, int]:
    # Own connections – the running test app keeps its own ones untouched.
    settings = get_settings()
    mongo = AsyncMongoClient(settings.mongo_url, tz_aware=True)
    engine = create_async_engine(settings.postgres_url)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            store = SecureFileStore(session, get_s3_storage(), get_storage())
            return await encrypt_existing(mongo[settings.mongo_db], store, owner_id)
    finally:
        await engine.dispose()
        await mongo.close()
