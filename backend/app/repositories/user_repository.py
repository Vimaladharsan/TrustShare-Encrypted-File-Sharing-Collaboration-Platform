"""Database access for users and roles. No business rules here – only reads and writes."""

import uuid

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MfaBackupCode, OAuthAccount, Role, User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        result = await self.session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        # The email column is CITEXT, so this match is case-insensitive.
        result = await self.session.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def get_role(self, name: str) -> Role:
        result = await self.session.execute(select(Role).where(Role.name == name))
        return result.scalar_one()

    async def add(self, user: User) -> User:
        self.session.add(user)
        await self.session.flush()  # sends the INSERT now so database defaults are filled in
        return user

    async def list_users(
        self, search: str | None, limit: int, offset: int
    ) -> tuple[list[User], int]:
        query = select(User)
        if search:
            pattern = f"%{search}%"
            query = query.where(or_(User.email.ilike(pattern), User.full_name.ilike(pattern)))
        total = await self.session.scalar(select(func.count()).select_from(query.subquery()))
        result = await self.session.execute(
            query.order_by(User.created_at.desc()).limit(limit).offset(offset)
        )
        return list(result.scalars().all()), total or 0

    # ---------- linked Google (OAuth) accounts ----------

    async def get_by_oauth(self, provider: str, provider_user_id: str) -> User | None:
        result = await self.session.execute(
            select(User)
            .join(OAuthAccount, OAuthAccount.user_id == User.id)
            .where(
                OAuthAccount.provider == provider,
                OAuthAccount.provider_user_id == provider_user_id,
            )
        )
        return result.scalar_one_or_none()

    async def link_oauth(
        self, user: User, provider: str, provider_user_id: str, email: str
    ) -> None:
        self.session.add(
            OAuthAccount(
                user_id=user.id, provider=provider, provider_user_id=provider_user_id, email=email
            )
        )

    async def delete(self, user_id: uuid.UUID) -> None:
        """Remove the account; OAuth links, MFA codes and file keys go with it (FK cascade)."""
        await self.session.execute(delete(User).where(User.id == user_id))

    async def count_active_with_role(self, role_name: str) -> int:
        count = await self.session.scalar(
            select(func.count())
            .select_from(User)
            .join(Role, User.role_id == Role.id)
            .where(Role.name == role_name, User.is_active.is_(True))
        )
        return count or 0

    # ---------- MFA backup codes ----------

    async def replace_backup_codes(self, user_id: uuid.UUID, code_hashes: list[str]) -> None:
        await self.session.execute(delete(MfaBackupCode).where(MfaBackupCode.user_id == user_id))
        self.session.add_all(MfaBackupCode(user_id=user_id, code_hash=h) for h in code_hashes)

    async def delete_backup_codes(self, user_id: uuid.UUID) -> None:
        await self.session.execute(delete(MfaBackupCode).where(MfaBackupCode.user_id == user_id))

    async def get_unused_backup_code(
        self, user_id: uuid.UUID, code_hash: str
    ) -> MfaBackupCode | None:
        result = await self.session.execute(
            select(MfaBackupCode).where(
                MfaBackupCode.user_id == user_id,
                MfaBackupCode.code_hash == code_hash,
                MfaBackupCode.used_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def count_unused_backup_codes(self, user_id: uuid.UUID) -> int:
        count = await self.session.scalar(
            select(func.count()).where(
                MfaBackupCode.user_id == user_id, MfaBackupCode.used_at.is_(None)
            )
        )
        return count or 0
