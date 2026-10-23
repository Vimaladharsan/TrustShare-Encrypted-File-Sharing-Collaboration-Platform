"""Database access for shares (PostgreSQL). No business rules here."""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import delete, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Share


class ShareRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, share: Share) -> Share:
        self.session.add(share)
        await self.session.flush()
        return share

    async def get(self, share_id: uuid.UUID) -> Share | None:
        return await self.session.get(Share, share_id)

    async def by_token_hash(self, token_hash: str) -> Share | None:
        result = await self.session.execute(select(Share).where(Share.token_hash == token_hash))
        return result.scalar_one_or_none()

    async def open_direct_share(self, file_id: str, recipient_id: uuid.UUID) -> Share | None:
        """The not-revoked direct share of this file with this person, if any."""
        result = await self.session.execute(
            select(Share).where(
                Share.file_id == file_id,
                Share.recipient_id == recipient_id,
                Share.revoked_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def for_file(self, file_id: str) -> Sequence[Share]:
        result = await self.session.execute(
            select(Share).where(Share.file_id == file_id).order_by(Share.created_at.desc())
        )
        return result.scalars().all()

    async def sent_by(self, owner_id: uuid.UUID, limit: int = 200) -> Sequence[Share]:
        result = await self.session.execute(
            select(Share)
            .where(Share.owner_id == owner_id)
            .order_by(Share.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()

    async def received_by(self, recipient_id: uuid.UUID) -> Sequence[Share]:
        """Direct shares to this person that are not revoked or expired (other checks follow)."""
        now = datetime.now(UTC)
        result = await self.session.execute(
            select(Share)
            .where(
                Share.recipient_id == recipient_id,
                Share.revoked_at.is_(None),
                or_(Share.expires_at.is_(None), Share.expires_at > now),
            )
            .order_by(Share.created_at.desc())
        )
        return result.scalars().all()

    async def claim_download(self, share_id: uuid.UUID) -> bool:
        """Count one download – atomically, so two visitors can't both take the last one."""
        result = await self.session.execute(
            update(Share)
            .where(
                Share.id == share_id,
                or_(Share.max_downloads.is_(None), Share.download_count < Share.max_downloads),
            )
            .values(download_count=Share.download_count + 1, last_accessed_at=datetime.now(UTC))
            .returning(Share.id)
        )
        return result.scalar_one_or_none() is not None

    async def touch(self, share_id: uuid.UUID) -> None:
        await self.session.execute(
            update(Share).where(Share.id == share_id).values(last_accessed_at=datetime.now(UTC))
        )

    async def delete_for_file(self, file_id: str) -> None:
        await self.session.execute(delete(Share).where(Share.file_id == file_id))
