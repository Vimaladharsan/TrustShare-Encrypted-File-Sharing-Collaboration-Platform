"""Secure vault: a private, password-protected place for a user's most sensitive files.

Rules (decided with Vimal, 27 Oct):
  - Extra encryption: every vault file's key is sealed with a key derived from the vault password
    (app/crypto/vault_crypto.py) inside the usual master-key envelope. Without the vault password
    nobody – not even someone with the database and the master keys – can open the files or read
    their names. A forgotten vault password can't be recovered; the vault can only be reset.
  - The password is checked on EVERY request (nothing stays "unlocked" on the server).
  - Private only: no sharing, no favorites, not in search, Recent or the normal file list.
  - 5 wrong passwords lock the vault for 15 minutes and raise a high-severity security event.
  - The activity log records what happened, never vault file names.
"""

import asyncio
import hashlib
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import Request, UploadFile
from pymongo.asynchronous.database import AsyncDatabase
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.permissions import Perm
from app.core.security import verify_password
from app.crypto import vault_crypto
from app.models import User, Vault
from app.repositories.favorite_repository import FavoriteRepository
from app.repositories.file_repository import FileRepository
from app.repositories.share_repository import ShareRepository
from app.schemas.vault import VaultFile, VaultPasswordChange, VaultReset, VaultStatus
from app.services.activity_service import ActivityService
from app.services.file_service import FileService
from app.services.file_validation import (
    ALLOWED_EXTENSIONS_TEXT,
    ALLOWED_TYPES,
    PREVIEWABLE,
    clean_filename,
    extension_of,
    office_structure_ok,
)
from app.services.security_events import record_security_event
from app.storage.secure_store import SecureFileStore


def _not_found() -> AppError:
    return AppError("VAULT_FILE_NOT_FOUND", "File not found in your vault.", 404)


def _wrong_password() -> AppError:
    # 403, not 401: a 401 would make the browser try to renew the login and send it again.
    return AppError("VAULT_PASSWORD_INCORRECT", "Wrong vault password.", 403)


class VaultGuard:
    """Wrong vault passwords: 5 in a row lock the vault for the lockout window (Redis)."""

    def __init__(self, redis: Redis) -> None:
        self.redis = redis
        settings = get_settings()
        self.max_failures = settings.max_failed_logins
        self.window = settings.lockout_minutes * 60

    async def locked_minutes(self, user_id: uuid.UUID) -> int:
        seconds = await self.redis.ttl(f"vault_lock:{user_id}")
        return -(-seconds // 60) if seconds > 0 else 0

    async def failure(self, user_id: uuid.UUID) -> bool:
        """Count one wrong password. Returns True if the vault is now locked."""
        key = f"vault_fail:{user_id}"
        failures = await self.redis.incr(key)
        if failures == 1:
            await self.redis.expire(key, self.window)
        if failures >= self.max_failures:
            await self.redis.set(f"vault_lock:{user_id}", "1", ex=self.window)
            await self.redis.delete(key)
            return True
        return False

    async def success(self, user_id: uuid.UUID) -> None:
        await self.redis.delete(f"vault_fail:{user_id}")

    async def clear(self, user_id: uuid.UUID) -> None:
        await self.redis.delete(f"vault_fail:{user_id}", f"vault_lock:{user_id}")


class VaultService:
    def __init__(
        self,
        session: AsyncSession,
        db: AsyncDatabase,
        redis: Redis,
        storage: SecureFileStore,
        request: Request,
    ) -> None:
        self.session = session
        self.db = db
        self.vault_files = db["vault_files"]
        self.files = FileRepository(db)
        self.storage = storage
        self.request = request
        self.activity = ActivityService(db)
        self.guard = VaultGuard(redis)

    # ---------- vault itself ----------

    async def status(self, user: User) -> VaultStatus:
        vault = await self.session.get(Vault, user.id)
        totals = await (
            await self.vault_files.aggregate(
                [
                    {"$match": {"owner_id": str(user.id)}},
                    {"$group": {"_id": None, "n": {"$sum": 1}, "bytes": {"$sum": "$size_bytes"}}},
                ]
            )
        ).to_list(length=1)
        return VaultStatus(
            available=Perm.FILE_UPLOAD in user.permission_codes,
            exists=vault is not None,
            file_count=totals[0]["n"] if totals else 0,
            size_bytes=totals[0]["bytes"] if totals else 0,
            locked_minutes=await self.guard.locked_minutes(user.id),
            created_at=vault.created_at if vault else None,
        )

    async def create(self, user: User, password: str) -> None:
        if await self.session.get(Vault, user.id) is not None:
            raise AppError("VAULT_EXISTS", "You already have a vault.", 409)
        await self._not_login_password(user, password)
        salt = vault_crypto.new_salt()
        key = await asyncio.to_thread(vault_crypto.derive_key, password, salt)
        self.session.add(
            Vault(
                user_id=user.id,
                salt=salt,
                kdf_n=vault_crypto.KDF_N,
                verifier=vault_crypto.verifier(key),
            )
        )
        await self.session.commit()
        await self._log(user, "vault.created")

    async def change_password(self, user: User, data: VaultPasswordChange) -> None:
        old_key = await self.unlock(user, data.current_password)
        await self._not_login_password(user, data.new_password)
        vault = await self.session.get(Vault, user.id)
        salt = vault_crypto.new_salt()
        new_key = await asyncio.to_thread(vault_crypto.derive_key, data.new_password, salt)

        docs = await self.vault_files.find({"owner_id": str(user.id)}).to_list(length=None)
        names = {}
        for doc in docs:  # re-lock every file key and name; the encrypted files don't change
            file_id = str(doc["_id"])
            await self.storage.rekey(doc, old_key, new_key)
            plain = vault_crypto.open_name(old_key, doc["name_sealed"], file_id)
            names[doc["_id"]] = vault_crypto.seal_name(new_key, plain, file_id)
        vault.salt, vault.kdf_n = salt, vault_crypto.KDF_N
        vault.verifier = vault_crypto.verifier(new_key)
        vault.password_changed_at = datetime.now(UTC)
        await self.session.commit()
        for file_oid, sealed in names.items():
            await self.vault_files.update_one({"_id": file_oid}, {"$set": {"name_sealed": sealed}})
        await self._log(user, "vault.password_changed", {"files": len(docs)})

    async def reset(self, user: User, data: VaultReset) -> int:
        """Forgot the vault password: prove it's the account owner, then delete everything."""
        if user.password_hash:
            if data.confirm.strip() != "DELETE":
                raise AppError("CONFIRMATION_MISMATCH", "Type DELETE to confirm.", 400)
            valid = data.account_password and await asyncio.to_thread(
                verify_password, data.account_password, user.password_hash
            )
            if not valid:
                raise AppError("WRONG_PASSWORD", "Your account password is not correct.", 400)
        elif data.confirm.strip().lower() != user.email.lower():
            raise AppError("CONFIRMATION_MISMATCH", "Type your email address to confirm.", 400)
        vault = await self.session.get(Vault, user.id)
        if vault is None:
            raise AppError("VAULT_NOT_FOUND", "You don't have a vault yet.", 404)
        docs = await self.vault_files.find({"owner_id": str(user.id)}).to_list(length=None)
        for doc in docs:
            await self.storage.delete(doc)  # encrypted object + key (crypto-shredding)
        await self.vault_files.delete_many({"owner_id": str(user.id)})
        await self.session.delete(vault)
        await self.session.commit()
        await self.guard.clear(user.id)
        await self._log(user, "vault.reset", {"files_deleted": len(docs)})
        return len(docs)

    # ---------- password check (every request) ----------

    async def unlock(self, user: User, password: str) -> bytes:
        """The vault key for this request, or an error. Wrong passwords count toward a lock."""
        vault = await self.session.get(Vault, user.id)
        if vault is None:
            raise AppError("VAULT_NOT_FOUND", "You don't have a vault yet.", 404)
        minutes = await self.guard.locked_minutes(user.id)
        if minutes:
            raise AppError(
                "VAULT_LOCKED",
                f"Too many wrong vault passwords. Try again in {minutes} minute(s).",
                429,
            )
        key = await asyncio.to_thread(vault_crypto.derive_key, password, vault.salt, vault.kdf_n)
        if not vault_crypto.matches(key, vault.verifier):
            await self._log(user, "vault.unlock_failed", status="failure")
            if await self.guard.failure(user.id):
                await record_security_event("vault_locked", request=self.request, user=user)
            raise _wrong_password()
        await self.guard.success(user.id)
        return key

    # ---------- files ----------

    async def list(self, user: User, password: str) -> list[VaultFile]:
        key = await self.unlock(user, password)
        docs = (
            await self.vault_files.find({"owner_id": str(user.id)})
            .sort("created_at", -1)
            .to_list(length=None)
        )
        return [self._info(key, doc) for doc in docs]

    async def upload(self, user: User, upload: UploadFile, password: str) -> VaultFile:
        key = await self.unlock(user, password)
        checks = FileService(self.db, self.storage, self.request)  # same checks as My Files
        name = clean_filename(upload.filename)
        extension = extension_of(name)
        try:
            if not name or extension not in ALLOWED_TYPES:
                raise AppError(
                    "UNSUPPORTED_FILE_TYPE",
                    f"This file type is not allowed. Allowed: {ALLOWED_EXTENSIONS_TEXT}.",
                    415,
                )
            used = await self.files.used_bytes(str(user.id))
            if used >= user.storage_quota_bytes:
                raise _quota_error()
            temp = self.storage.temp_path(uuid.uuid4().hex)
            try:
                size, _ = await checks.receive_upload(upload, temp, extension)
                if used + size > user.storage_quota_bytes:
                    raise _quota_error()
                if not await asyncio.to_thread(office_structure_ok, extension, temp):
                    raise AppError(
                        "UNSUPPORTED_FILE_TYPE",
                        "The file's content does not match its extension.",
                        415,
                    )
                file_oid = ObjectId()
                stored = await self.storage.store(str(file_oid), user.id, temp, vault_key=key)
            finally:
                await asyncio.to_thread(temp.unlink, missing_ok=True)
        except AppError as exc:
            await checks.report_rejected_upload(user, name, exc)
            await self._log(user, "vault.upload_rejected", {"reason": exc.code}, status="failure")
            raise

        now = datetime.now(UTC)
        file_type = ALLOWED_TYPES[extension]
        doc = {
            "_id": file_oid,
            "owner_id": str(user.id),
            "name_sealed": vault_crypto.seal_name(key, name, str(file_oid)),
            "extension": extension,
            "mime_type": file_type.mime_type,
            "category": file_type.category,
            "size_bytes": size,
            **stored,
            "created_at": now,
            "updated_at": now,
        }
        try:
            await self.vault_files.insert_one(doc)
        except Exception:
            await self.storage.delete(doc)
            raise
        await self._log(user, "vault.file_added", {"extension": extension, "size_bytes": size})
        return self._info(key, doc)

    async def open(
        self, user: User, file_id: str, password: str, preview: bool
    ) -> tuple[dict[str, Any], AsyncIterator[bytes]]:
        key = await self.unlock(user, password)
        doc = await self._owned(user, file_id)
        if preview and doc["extension"] not in PREVIEWABLE:
            raise AppError("PREVIEW_NOT_SUPPORTED", "This file type can't be previewed.", 415)
        chunks = await self.storage.open(doc, vault_key=key)
        await self._log(user, "vault.file_previewed" if preview else "vault.file_downloaded")
        # Response helpers expect the plain name; it exists only in this response.
        return {
            **doc,
            "original_name": vault_crypto.open_name(key, doc["name_sealed"], file_id),
        }, chunks

    async def rename(self, user: User, file_id: str, password: str, new_name: str) -> VaultFile:
        key = await self.unlock(user, password)
        doc = await self._owned(user, file_id)
        name = clean_filename(new_name)
        if not name or extension_of(name) != doc["extension"]:
            raise AppError(
                "INVALID_NAME", f"Keep the .{doc['extension']} extension when renaming.", 400
            )
        sealed = vault_crypto.seal_name(key, name, file_id)
        await self.vault_files.update_one(
            {"_id": doc["_id"]}, {"$set": {"name_sealed": sealed, "updated_at": datetime.now(UTC)}}
        )
        await self._log(user, "vault.file_renamed")
        return self._info(key, {**doc, "name_sealed": sealed})

    async def delete(self, user: User, file_id: str, password: str) -> None:
        await self.unlock(user, password)
        doc = await self._owned(user, file_id)
        await self.storage.delete(doc)  # permanent – the vault has no trash
        await self.vault_files.delete_one({"_id": doc["_id"]})
        await self._log(user, "vault.file_deleted")

    async def move_in(self, user: User, file_id: str, password: str) -> VaultFile:
        """A file from My Files into the vault. Its shares and favorite are removed; only its key
        is re-locked (the encrypted bytes stay where they are)."""
        key = await self.unlock(user, password)
        doc = await self.files.get(file_id)
        if doc is None or doc["owner_id"] != str(user.id) or doc["status"] != "active":
            raise AppError("FILE_NOT_FOUND", "File not found.", 404)
        if not doc.get("encryption"):
            raise AppError("FILE_NOT_ENCRYPTED", "This file must be encrypted first.", 409)

        vault_doc = {
            "_id": doc["_id"],
            "owner_id": doc["owner_id"],
            "name_sealed": vault_crypto.seal_name(key, doc["original_name"], file_id),
            **{k: doc[k] for k in ("extension", "mime_type", "category", "size_bytes")},
            **{k: doc[k] for k in ("storage_backend", "storage_key", "encryption")},
            "created_at": doc["created_at"],
            "updated_at": datetime.now(UTC),
        }
        await self.vault_files.insert_one(vault_doc)
        try:
            await self.storage.rekey(doc, None, key)
            await ShareRepository(self.session).delete_for_file(file_id)
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            await self.vault_files.delete_one({"_id": doc["_id"]})
            raise
        await self.db["files"].delete_one({"_id": doc["_id"]})
        await FavoriteRepository(self.db).remove(str(user.id), file_id)
        await self._log(user, "vault.file_moved_in", {"extension": doc["extension"]})
        return self._info(key, vault_doc)

    async def move_out(self, user: User, file_id: str, password: str) -> dict[str, Any]:
        """Back to My Files (top level) – a normal file again, readable without the vault."""
        key = await self.unlock(user, password)
        doc = await self._owned(user, file_id)
        name = vault_crypto.open_name(key, doc["name_sealed"], file_id)
        digest = hashlib.sha256()  # My Files needs the fingerprint for duplicate detection
        async for chunk in await self.storage.open(doc, vault_key=key):
            digest.update(chunk)

        now = datetime.now(UTC)
        file_doc = {
            "_id": doc["_id"],
            "owner_id": doc["owner_id"],
            "folder_id": None,
            "original_name": name,
            "name_lower": name.lower(),
            **{k: doc[k] for k in ("extension", "mime_type", "category", "size_bytes")},
            "sha256": digest.hexdigest(),
            **{k: doc[k] for k in ("storage_backend", "storage_key", "encryption")},
            "version": 1,
            "status": "active",
            "trashed_at": None,
            "created_at": doc["created_at"],
            "updated_at": now,
        }
        await self.files.insert(file_doc)
        try:
            await self.storage.rekey(doc, key, None)
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            await self.db["files"].delete_one({"_id": doc["_id"]})
            raise
        await self.vault_files.delete_one({"_id": doc["_id"]})
        await self._log(user, "vault.file_moved_out", {"extension": doc["extension"]})
        return file_doc

    # ---------- helpers ----------

    async def _owned(self, user: User, file_id: str) -> dict[str, Any]:
        try:
            oid = ObjectId(file_id)
        except (InvalidId, TypeError) as exc:
            raise _not_found() from exc
        doc = await self.vault_files.find_one({"_id": oid, "owner_id": str(user.id)})
        if doc is None:
            raise _not_found()
        return doc

    async def _not_login_password(self, user: User, password: str) -> None:
        if user.password_hash and await asyncio.to_thread(
            verify_password, password, user.password_hash
        ):
            raise AppError(
                "VAULT_PASSWORD_REUSED",
                "Use a different password from your login password.",
                400,
            )

    @staticmethod
    def _info(key: bytes, doc: dict[str, Any]) -> VaultFile:
        file_id = str(doc["_id"])
        return VaultFile(
            id=file_id,
            name=vault_crypto.open_name(key, doc["name_sealed"], file_id),
            extension=doc["extension"],
            category=doc["category"],
            size_bytes=doc["size_bytes"],
            can_preview=doc["extension"] in PREVIEWABLE,
            created_at=doc["created_at"],
        )

    async def _log(
        self,
        user: User,
        action: str,
        details: dict[str, Any] | None = None,
        status: str = "success",
    ) -> None:
        # Never a vault file name in the log: the log is readable by admins.
        await self.activity.log(
            self.request, user, action, resource_type="vault", status=status, details=details
        )


def _quota_error() -> AppError:
    return AppError("QUOTA_EXCEEDED", "Not enough storage space left.", 413)
