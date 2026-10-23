"""Master-key rotation and "keys never leak" (Milestone 2, Phase 6).

Rotation tests use their OWN keyring (current keys + a throwaway v2) and only touch the test user's
keys, so the developer's real files are never re-wrapped with a key the app doesn't have."""

import asyncio
import base64
import logging
import os
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import pytest
from bson import ObjectId
from fastapi.testclient import TestClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.crypto.keyring import Keyring, get_keyring, parse_master_keys
from app.models import FileKey
from app.scripts.rotate_keys import rotate
from app.services.encryption_service import (
    DecryptionError,
    EncryptedKey,
    EncryptionService,
    decrypt_bytes,
)
from tests.conftest import file_key_row, share_row, stored_object
from tests.test_files import PDF, auth, mongo_db, new_user, upload


def rotated_keyring() -> Keyring:
    """The configured master keys plus a new version, made active."""
    keys = parse_master_keys(get_settings().master_keys.get_secret_value())
    new_version = max(keys) + 1
    return Keyring({**keys, new_version: os.urandom(32)}, new_version)


async def _rotate(keyring: Keyring, owner_id: str) -> dict[str, int]:
    engine = create_async_engine(get_settings().postgres_url)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            return await rotate(session, EncryptionService(keyring), 2, uuid.UUID(owner_id))
    finally:
        await engine.dispose()


async def _set_key_version(file_id: str, version: int) -> None:
    engine = create_async_engine(get_settings().postgres_url)
    try:
        async with async_sessionmaker(engine)() as session:
            await session.execute(
                update(FileKey).where(FileKey.file_id == file_id).values(key_version=version)
            )
            await session.commit()
    finally:
        await engine.dispose()


def user_with_files(client: TestClient, email: str, count: int) -> tuple[str, str, list[str]]:
    token = new_user(client, email)
    owner_id = client.get("/api/users/me", headers=auth(token)).json()["id"]
    ids = [
        upload(client, token, f"f{i}.pdf", PDF, allow_duplicate="true").json()["id"]
        for i in range(count)
    ]
    return token, owner_id, ids


# ---------- rotation ----------


def test_rotation_rewraps_every_key_without_touching_the_files(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    _, owner_id, file_ids = user_with_files(client, new_email(), 3)  # 3 keys, batch size 2
    before = {fid: file_key_row(fid) for fid in file_ids}
    objects = {fid: stored_object(_key(fid)) for fid in file_ids}
    keyring = rotated_keyring()

    result = asyncio.run(_rotate(keyring, owner_id))

    assert result == {"active_version": keyring.active_version, "rotated": 3, "failed": 0}
    for fid in file_ids:
        row = file_key_row(fid)
        assert row.key_version == keyring.active_version and row.rotated_at is not None
        assert row.wrapped_key != before[fid].wrapped_key
        assert stored_object(_key(fid)) == objects[fid]  # ciphertext untouched
        # The re-wrapped key still opens the very same file.
        dek = EncryptionService(keyring).open_file_key(
            fid, EncryptedKey(row.wrapped_key, row.key_version)
        )
        assert decrypt_bytes(dek, fid, objects[fid]) == PDF


def test_rotation_can_be_run_again_safely(client: TestClient, new_email: Callable[[], str]) -> None:
    _, owner_id, _ = user_with_files(client, new_email(), 1)
    keyring = rotated_keyring()

    first = asyncio.run(_rotate(keyring, owner_id))
    second = asyncio.run(_rotate(keyring, owner_id))

    assert first["rotated"] == 1
    assert second["rotated"] == 0


def test_old_master_key_alone_cannot_open_rotated_keys(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    _, owner_id, (file_id,) = user_with_files(client, new_email(), 1)
    asyncio.run(_rotate(rotated_keyring(), owner_id))
    row = file_key_row(file_id)

    with pytest.raises(DecryptionError):
        EncryptionService(get_keyring()).open_file_key(
            file_id, EncryptedKey(row.wrapped_key, row.key_version)
        )


def test_key_with_missing_master_key_is_reported_not_changed(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    _, owner_id, (file_id,) = user_with_files(client, new_email(), 1)
    asyncio.run(_set_key_version(file_id, 99))  # a version nobody has
    before = file_key_row(file_id)

    result = asyncio.run(_rotate(rotated_keyring(), owner_id))

    assert result["rotated"] == 0 and result["failed"] == 1
    assert file_key_row(file_id).wrapped_key == before.wrapped_key


# ---------- keys and tokens never leak ----------


def test_no_key_material_or_link_token_in_logs(
    client: TestClient, new_email: Callable[[], str], caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    token, owner_id, (file_id,) = user_with_files(client, new_email(), 1)
    client.get(f"/api/files/{file_id}/download", headers=auth(token))
    expires = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    link = client.post(
        f"/api/files/{file_id}/shares",
        json={"share_type": "link", "permission": "download", "expires_at": expires},
        headers=auth(token),
    ).json()
    link_token = link["url"].rsplit("/s/", 1)[1]
    client.get(f"/api/s/{link_token}/download")
    asyncio.run(_rotate(rotated_keyring(), owner_id))

    # Only the backend's own log lines (the test HTTP client logs its URLs separately).
    app_log = "\n".join(
        record.getMessage() for record in caplog.records if not record.name.startswith("httpx")
    )
    secrets = _master_key_strings() + [
        link_token,
        share_row(link["id"]).token_hash,
        file_key_row(file_id).wrapped_key.hex(),
        base64.b64encode(file_key_row(file_id).wrapped_key).decode(),
    ]
    for secret in secrets:
        assert secret not in app_log
    assert "/api/s/***/download" in app_log


def test_no_key_material_in_activity_logs(client: TestClient, new_email: Callable[[], str]) -> None:
    token, owner_id, (file_id,) = user_with_files(client, new_email(), 1)
    client.get(f"/api/files/{file_id}/download", headers=auth(token))

    logs = str(list(mongo_db()["activity_logs"].find({"user_id": owner_id})))

    for secret in _master_key_strings() + [file_key_row(file_id).wrapped_key.hex()]:
        assert secret not in logs
    assert "wrapped" not in logs


def test_objects_holding_keys_print_safely(
    client: TestClient, new_email: Callable[[], str]
) -> None:
    _, _, (file_id,) = user_with_files(client, new_email(), 1)
    printed = " ".join([repr(get_settings()), repr(get_keyring()), repr(file_key_row(file_id))])

    for secret in _master_key_strings():
        assert secret not in printed
    assert file_key_row(file_id).wrapped_key.hex() not in printed


def _master_key_strings() -> list[str]:
    raw = get_settings().master_keys.get_secret_value()
    return [part.split(":", 1)[1] for part in raw.split(",")]


def _key(file_id: str) -> str:
    return mongo_db()["files"].find_one({"_id": ObjectId(file_id)})["storage_key"]
