"""Erasing an account and everything it owns – used by "Delete my account" (the user) and by an
admin deleting an account that has been inactive for 30+ days. One implementation, so both
remove exactly the same things.

Removed: every encrypted object and its key (crypto-shredding), file metadata, vault files,
folders, favorites, shares (database cascade), MFA codes, Google links and the vault row
(cascade), all sessions, any lockout – then the account row.
The activity log is kept: it is the audit trail.
"""

from typing import Any

from pymongo.asynchronous.database import AsyncDatabase
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.repositories.favorite_repository import FavoriteRepository
from app.repositories.file_repository import FileRepository
from app.repositories.folder_repository import FolderRepository
from app.repositories.user_repository import UserRepository
from app.services.login_guard import LoginGuard
from app.services.session_service import SessionService
from app.storage.secure_store import SecureFileStore


async def erase_account(
    user: User,
    *,
    session: AsyncSession,
    db: AsyncDatabase,
    redis: Redis,
    storage: SecureFileStore,
) -> dict[str, Any]:
    """Delete the account and all its data. Safe to repeat if it was interrupted."""
    owner_id, user_id = str(user.id), user.id
    files = FileRepository(db)
    owned = await files.all_owned(owner_id)
    for doc in owned:  # deleting a missing object is a no-op, so a retry is harmless
        await storage.delete(doc)  # encrypted object + its key + its shares
    await files.delete_all_owned(owner_id)
    vault = db["vault_files"]
    vault_docs = await vault.find({"owner_id": owner_id}).to_list(length=None)
    for doc in vault_docs:  # the vault row itself goes with the user (database cascade)
        await storage.delete(doc)
    await vault.delete_many({"owner_id": owner_id})
    await FolderRepository(db).delete_all_owned(owner_id)
    await FavoriteRepository(db).delete_for_user(owner_id)

    await UserRepository(session).delete(user_id)
    await session.commit()
    await SessionService(redis).revoke_all(user_id)  # logged out everywhere, tokens rejected
    await LoginGuard(redis).unlock(user_id)
    return {
        "files_deleted": len(owned) + len(vault_docs),
        "bytes_freed": sum(doc["size_bytes"] for doc in [*owned, *vault_docs]),
    }
