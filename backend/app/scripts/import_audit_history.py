"""Bring the activity history recorded before Milestone 3 into the hash-chained audit log.

    docker compose exec backend python -m app.scripts.import_audit_history

Imports every activity_logs record that happened before the audit log's first entry (or all of
them if the audit log is empty), oldest first, flagged `imported`. Safe to run again: records that
were already imported are skipped. Run it once right after deploying Milestone 3.
"""

import asyncio

from app.audit.service import AuditService
from app.core.config import get_settings
from app.db.mongo import close_mongo, get_mongo, init_mongo


async def run() -> int:
    init_mongo(get_settings())
    db = get_mongo()
    audit = AuditService(db)
    try:
        await audit._ensure_indexes()
        first_live = await audit.collection.find_one(
            {"imported": {"$ne": True}}, {"created_at": 1}, sort=[("seq", 1)]
        )
        match = {"created_at": {"$lt": first_live["created_at"]}} if first_live else {}
        done = set(await audit.collection.distinct("source_activity_id", {"imported": True}))
        imported = 0
        async for activity in db["activity_logs"].find(match).sort("created_at", 1):
            if activity["_id"] in done:
                continue
            await audit.append(activity, None, imported=True)
            imported += 1
        result = await audit.verify()
        print(
            f"Imported {imported} historical activities. Chain valid: {result.valid} "
            f"({result.checked} entries checked)."
        )
        return imported
    finally:
        await close_mongo()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
