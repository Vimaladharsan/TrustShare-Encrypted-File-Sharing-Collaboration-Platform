"""My account overview: a security score with a checklist, and a few account statistics.

The score is the sum of the points of every check that passes (100 = everything in place). Each
check tells the web app which setting fixes it, so the profile page can offer a "Fix now" button.
"""

from datetime import UTC, datetime, timedelta

from fastapi import Request
from pymongo.asynchronous.database import AsyncDatabase
from redis.asyncio import Redis
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.user_agent import describe_device
from app.models import MfaBackupCode, Share, User
from app.models.vault import Vault
from app.repositories.file_repository import FileRepository
from app.schemas.user import AccountOverview, AccountStats, LastSignIn, SecurityCheck
from app.services.account_service import AccountService

PASSWORD_MAX_AGE_DAYS = 180
MAX_DEVICES = 3
MIN_BACKUP_CODES = 3
FAILED_SIGN_IN_DAYS = 7


def _grade(score: int) -> str:
    return "strong" if score >= 85 else "good" if score >= 60 else "needs_attention"


class AccountOverviewService:
    def __init__(
        self, session: AsyncSession, redis: Redis, db: AsyncDatabase, request: Request
    ) -> None:
        self.session = session
        self.db = db
        self.account = AccountService(session, redis, db, request)

    async def overview(self, user: User) -> AccountOverview:
        now = datetime.now(UTC)
        checks = [
            SecurityCheck(
                key="two_step",
                label="Two-step verification",
                points=30,
                ok=user.mfa_enabled,
                detail="A code from your phone is needed to sign in."
                if user.mfa_enabled
                else "Turn it on so a stolen password alone can't open your account.",
                fix="security",
            ),
            SecurityCheck(
                key="email_verified",
                label="Email address verified",
                points=15,
                ok=user.is_email_verified,
                detail="We can reach you about your account."
                if user.is_email_verified
                else "Confirm your address so security notices and resets reach you.",
                fix="verify_email",
            ),
            await self._failed_sign_ins(user, now),
            await self._backup_codes(user),
            self._password(user, now),
            await self._devices(user),
            await self._vault(user),
        ]
        score = sum(c.points for c in checks if c.ok)
        return AccountOverview(
            score=score, grade=_grade(score), checks=checks, stats=await self._stats(user, now)
        )

    # ---------- checks ----------

    async def _failed_sign_ins(self, user: User, now: datetime) -> SecurityCheck:
        failed = await self.db["activity_logs"].count_documents(
            {
                "action": {"$in": ["auth.login.failed", "auth.login.locked"]},
                "created_at": {"$gte": now - timedelta(days=FAILED_SIGN_IN_DAYS)},
                "$or": [{"user_id": str(user.id)}, {"details.email": user.email.lower()}],
            }
        )
        return SecurityCheck(
            key="failed_sign_ins",
            label=f"No failed sign-ins in the last {FAILED_SIGN_IN_DAYS} days",
            points=15,
            ok=failed == 0,
            detail="Nobody tried a wrong password on your account."
            if failed == 0
            else f"{failed} failed sign-in attempt{'s' if failed != 1 else ''} – check your "
            "activity and change your password if it wasn't you.",
            fix="activity",
        )

    async def _backup_codes(self, user: User) -> SecurityCheck:
        if not user.mfa_enabled:
            return SecurityCheck(
                key="backup_codes",
                label="Backup codes ready",
                points=10,
                ok=False,
                detail="Available once two-step verification is on.",
                fix="security",
            )
        left = await self.session.scalar(
            select(func.count())
            .select_from(MfaBackupCode)
            .where(MfaBackupCode.user_id == user.id, MfaBackupCode.used_at.is_(None))
        )
        ok = (left or 0) >= MIN_BACKUP_CODES
        return SecurityCheck(
            key="backup_codes",
            label="Backup codes ready",
            points=10,
            ok=ok,
            detail=f"{left} unused backup codes for when your phone is lost."
            if ok
            else f"Only {left} left – create new backup codes.",
            fix="security",
        )

    @staticmethod
    def _password(user: User, now: datetime) -> SecurityCheck:
        if user.password_hash is None:
            return SecurityCheck(
                key="password_age",
                label="Password",
                points=10,
                ok=True,
                detail="You sign in with Google – there is no TrustShare password to keep fresh.",
                fix="security",
            )
        changed = user.password_changed_at or user.created_at
        days = max(0, (now - changed).days)
        ok = days <= PASSWORD_MAX_AGE_DAYS
        return SecurityCheck(
            key="password_age",
            label="Password changed recently",
            points=10,
            ok=ok,
            detail=(
                "Changed today."
                if days == 0
                else f"Last changed {days} day{'s' if days != 1 else ''} ago."
            )
            if ok
            else f"Last changed {days} days ago – consider a new one.",
            fix="security",
        )

    async def _devices(self, user: User) -> SecurityCheck:
        count = len(await self.account.devices(user, None))
        ok = count <= MAX_DEVICES
        return SecurityCheck(
            key="devices",
            label=f"Signed in on {MAX_DEVICES} devices or fewer",
            points=10,
            ok=ok,
            detail=f"Signed in on {count} device{'s' if count != 1 else ''}."
            if ok
            else f"Signed in on {count} devices – sign out the ones you don't use.",
            fix="devices",
        )

    async def _vault(self, user: User) -> SecurityCheck:
        exists = await self.session.get(Vault, user.id) is not None
        return SecurityCheck(
            key="vault",
            label="Secure vault set up",
            points=10,
            ok=exists,
            detail="Your most sensitive files get a second password."
            if exists
            else "Set up the vault for files that need an extra password.",
            fix="vault",
        )

    # ---------- statistics ----------

    async def _stats(self, user: User, now: datetime) -> AccountStats:
        owner = str(user.id)
        files = await self.db["files"].count_documents({"owner_id": owner, "status": "active"})
        files += await self.db["vault_files"].count_documents({"owner_id": owner})
        active_shares = await self.session.scalar(
            select(func.count())
            .select_from(Share)
            .where(
                Share.owner_id == user.id,
                Share.revoked_at.is_(None),
                or_(Share.expires_at.is_(None), Share.expires_at > now),
            )
        )
        # The sign-in before this one: a quick way to notice a visit you didn't make.
        logins = (
            await self.db["activity_logs"]
            .find({"user_id": owner, "action": "auth.login.success"})
            .sort("created_at", -1)
            .limit(2)
            .to_list(length=2)
        )
        previous = logins[1] if len(logins) > 1 else (logins[0] if logins else None)
        last = None
        if previous:
            device = describe_device(previous.get("user_agent", ""))
            last = LastSignIn(
                at=previous["created_at"], device=f"{device['browser']} on {device['os']}"
            )
        return AccountStats(
            member_since=user.created_at,
            files=files,
            storage_used_bytes=await FileRepository(self.db).used_bytes(owner),
            storage_quota_bytes=user.storage_quota_bytes,
            active_shares=active_shares or 0,
            previous_sign_in=last,
        )
