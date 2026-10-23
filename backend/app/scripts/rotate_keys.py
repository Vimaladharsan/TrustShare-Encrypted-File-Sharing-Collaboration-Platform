"""Master-key rotation: re-wrap every file key with the active master key. Files are NOT
re-encrypted – only the small wrapped keys in PostgreSQL change (docs/key-management.md §4.4).

    docker compose exec backend python -m app.scripts.rotate_keys --status
    docker compose exec backend python -m app.scripts.rotate_keys --new-key
    docker compose exec backend python -m app.scripts.rotate_keys

Procedure:
  1. --new-key prints the next version and a fresh random master key (the only time a key is
     printed – put it straight into .env / the secret manager and a separate backup).
  2. Append it to MASTER_KEYS, set ACTIVE_MASTER_KEY_VERSION to the new version and restart the
     backend: new uploads use the new key immediately, old files still open with the old one.
  3. Run without options: every key still on an older version is unwrapped and re-wrapped with
     the new key, in batches (one transaction each). Safe to stop and run again.
  4. When --status shows no keys on old versions, remove the old key from MASTER_KEYS.
"""

import argparse
import asyncio
import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.crypto.keyring import get_keyring, new_master_key
from app.db.mongo import close_mongo, get_mongo, init_mongo
from app.repositories.file_key_repository import FileKeyRepository
from app.services.encryption_service import DecryptionError, EncryptedKey, EncryptionService

logger = logging.getLogger(__name__)


async def rotate(
    session: AsyncSession,
    encryption: EncryptionService,
    batch_size: int = 100,
    owner_id: uuid.UUID | None = None,
) -> dict[str, int]:
    """Re-wrap all keys not on the active master-key version. Returns counts.
    Keys that can't be unwrapped (their master key is missing) are reported, never changed."""
    keys = FileKeyRepository(session)
    active = encryption.keyring.active_version
    rotated, failed = 0, set()
    while rows := await keys.older_than(active, batch_size, owner_id=owner_id, skip=failed):
        for row in rows:
            try:
                new_key = encryption.rewrap(
                    row.file_id, EncryptedKey(row.wrapped_key, row.key_version)
                )
            except DecryptionError:
                logger.error(
                    "Could not unwrap key of file %s (version %d)", row.file_id, row.key_version
                )
                failed.add(row.file_id)
                continue
            await keys.replace(row, new_key)
            rotated += 1
        await session.commit()  # one transaction per batch
    return {"active_version": active, "rotated": rotated, "failed": len(failed)}


async def _status(session: AsyncSession) -> dict[int, int]:
    return await FileKeyRepository(session).count_by_version()


def _print_status(counts: dict[int, int], active: int) -> None:
    if not counts:
        print("No file keys yet.")
    for version, count in sorted(counts.items()):
        marker = " (active)" if version == active else " ← old, re-wrap with rotate_keys"
        print(f"  master key v{version}: {count} file key(s){marker}")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Rotate TrustShare master keys")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--status", action="store_true", help="show keys per master-key version")
    group.add_argument("--new-key", action="store_true", help="print the next master key to add")
    args = parser.parse_args()

    keyring = get_keyring()
    if args.new_key:
        version = max(keyring.versions) + 1
        print("Add this to MASTER_KEYS in .env (comma-separated), set")
        print(f"ACTIVE_MASTER_KEY_VERSION={version}, restart the backend, then run rotate_keys.")
        print("Keep a separate, secure backup – losing a master key makes its files unreadable.\n")
        print(f"{version}:{new_master_key()}")
        return

    settings = get_settings()
    engine = create_async_engine(settings.postgres_url)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            print(f"Configured master keys: {keyring.versions}, active: v{keyring.active_version}")
            _print_status(await _status(session), keyring.active_version)
            if args.status:
                return
            result = await rotate(session, EncryptionService(keyring))
            print(f"\nRe-wrapped {result['rotated']} key(s); {result['failed']} failed.")
            _print_status(await _status(session), keyring.active_version)
    finally:
        await engine.dispose()

    # Audit trail: who rotated is the operator on the server; record what happened.
    init_mongo(settings)
    try:
        await get_mongo()["activity_logs"].insert_one(
            {
                "user_id": None,
                "actor_email": "system:rotate_keys",
                "action": "key.rotate",
                "resource_type": "file_keys",
                "resource_id": None,
                "status": "success" if result["failed"] == 0 else "failure",
                "ip_address": None,
                "user_agent": "rotate_keys script",
                "request_id": None,
                "details": result,
                "created_at": datetime.now(UTC),
            }
        )
    finally:
        await close_mongo()


if __name__ == "__main__":
    asyncio.run(main())
