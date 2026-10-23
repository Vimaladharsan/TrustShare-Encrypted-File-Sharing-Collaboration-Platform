"""The one place where file bytes are stored and read.

Encrypted on the way in, decrypted on the way out:

    store(file_id, owner, plaintext file)  → new random key → AES-256-GCM chunks → private bucket,
                                             wrapped key → PostgreSQL file_keys
    open(file metadata)                    → wrapped key → unwrap → stream object → verify + decrypt
    delete(file metadata)                  → remove object AND key (without the key the bytes are
                                             unreadable forever – "crypto-shredding")

Services (FileService, FolderService, TrashService) only ever call these three methods; they never
see keys. Files uploaded before Milestone 2 (plaintext on local disk, `encryption: null`) are still
readable through the same methods until `app.scripts.encrypt_existing_files` has converted them.
"""

import asyncio
import logging
import uuid
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.db.postgres import get_db
from app.repositories.file_key_repository import FileKeyRepository
from app.services.encryption_service import (
    ALGORITHM,
    CHUNK_SIZE,
    FORMAT,
    DecryptionError,
    EncryptionService,
    decrypt_stream,
    encrypt_file,
)
from app.storage.local import LocalStorage, get_storage
from app.storage.s3 import S3Storage, get_s3_storage

logger = logging.getLogger(__name__)


def integrity_error() -> AppError:
    return AppError(
        "FILE_INTEGRITY_ERROR",
        "This file failed its security check and can't be opened. Please contact support.",
        500,
    )


class SecureFileStore:
    def __init__(
        self,
        session: AsyncSession,
        objects: S3Storage,
        legacy: LocalStorage,
        encryption: EncryptionService | None = None,
    ) -> None:
        self.session = session
        self.keys = FileKeyRepository(session)
        self.objects = objects
        self.legacy = legacy
        self.encryption = encryption or EncryptionService()

    def temp_path(self, name: str) -> Path:
        """Where uploads are written while they're still being checked (local, short-lived)."""
        return self.legacy.temp_path(name)

    # ---------- write ----------

    async def store(self, file_id: str, owner_id: uuid.UUID, plaintext: Path) -> dict[str, Any]:
        """Encrypt a validated file and store it. Returns the storage fields for the metadata."""
        dek, wrapped = self.encryption.new_file_key(file_id)
        encrypted = plaintext.with_name(plaintext.name + ".enc")
        key = f"{owner_id}/{uuid.uuid4()}"  # random object name – never the user's filename
        try:
            size = await asyncio.to_thread(_encrypt_to, dek, file_id, plaintext, encrypted)
            await self.objects.save(key, encrypted)
        finally:
            await asyncio.to_thread(encrypted.unlink, missing_ok=True)
            del dek  # the raw key is not kept anywhere
        try:
            await self.keys.add(file_id, owner_id, wrapped)
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            await self.objects.delete(key)  # no orphaned ciphertext without a key
            raise
        return {
            "storage_backend": "s3",
            "storage_key": key,
            "encryption": {
                "algorithm": ALGORITHM,
                "format": FORMAT,
                "chunk_size": CHUNK_SIZE,
                "encrypted_size": size,
            },
        }

    # ---------- read ----------

    async def open(self, doc: dict[str, Any]) -> AsyncIterator[bytes]:
        """Verified plaintext of a stored file. Raises AppError before anything is sent if the
        key is missing or the first chunk fails its integrity check."""
        if not doc.get("encryption"):
            return self.legacy.open(doc["storage_key"])  # Milestone 1 file, not yet converted

        file_id = str(doc["_id"])
        stored = await self.keys.get(file_id)
        if stored is None:
            logger.error("Encryption key missing for file %s", file_id)
            raise integrity_error()
        try:
            dek = self.encryption.open_file_key(file_id, stored)
        except DecryptionError as exc:
            logger.error("Could not unwrap the key of file %s: %s", file_id, exc)
            raise integrity_error() from exc

        plaintext = decrypt_stream(dek, file_id, self.objects.open(doc["storage_key"]))
        try:
            first = await anext(plaintext)  # check the start now, so errors become a clean 500
        except DecryptionError as exc:
            logger.error("Integrity check failed for file %s: %s", file_id, exc)
            raise integrity_error() from exc
        return _chain(first, plaintext, file_id)

    # ---------- delete ----------

    async def delete(self, doc: dict[str, Any]) -> None:
        if not doc.get("encryption"):
            await self.legacy.delete(doc["storage_key"])
            return
        await self.objects.delete(doc["storage_key"])
        await self.keys.delete(str(doc["_id"]))
        await self.session.commit()


def _encrypt_to(dek: bytes, file_id: str, source: Path, target: Path) -> int:
    with source.open("rb") as src, target.open("wb") as dst:
        return encrypt_file(dek, file_id, src, dst)


async def _chain(first: bytes, rest: AsyncIterator[bytes], file_id: str) -> AsyncIterator[bytes]:
    yield first
    try:
        async for chunk in rest:
            yield chunk
    except DecryptionError:
        # Headers are already sent: stop the transfer so the client gets an incomplete download
        # instead of unverified data.
        logger.error("Integrity check failed mid-download for file %s", file_id)
        raise


def get_file_store(session: AsyncSession = Depends(get_db)) -> SecureFileStore:
    """FastAPI dependency."""
    return SecureFileStore(session, get_s3_storage(), get_storage())
