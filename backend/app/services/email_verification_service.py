"""Email verification: prove the address belongs to the person who signed up.

Redis keys (expire automatically):
    email_verify:{sha256(token)}   -> user_id   (24 h, single use)
    email_verify_user:{user_id}    -> hash of the latest token (a new email cancels the old link)

By default verification is "soft": unverified users can still log in and see a reminder.
REQUIRE_EMAIL_VERIFICATION=true makes it strict (login refused until verified).
"""

import uuid

from fastapi import Request
from pymongo.asynchronous.database import AsyncDatabase
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.security import hash_token, new_url_token
from app.models import User
from app.repositories.user_repository import UserRepository
from app.services.activity_service import ActivityService
from app.services.email_service import Email, verification_email


class EmailVerificationService:
    def __init__(
        self, session: AsyncSession, redis: Redis, db: AsyncDatabase, request: Request
    ) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.redis = redis
        self.activity = ActivityService(db)
        self.request = request

    async def create_email(self, user: User) -> Email:
        """New verification link for this user (the previous one stops working)."""
        settings = get_settings()
        ttl = settings.email_verification_hours * 3600
        token = new_url_token()
        token_hash = hash_token(token)

        old_hash = await self.redis.get(f"email_verify_user:{user.id}")
        async with self.redis.pipeline(transaction=True) as pipe:
            if old_hash:
                pipe.delete(f"email_verify:{old_hash}")
            pipe.set(f"email_verify:{token_hash}", str(user.id), ex=ttl)
            pipe.set(f"email_verify_user:{user.id}", token_hash, ex=ttl)
            await pipe.execute()

        link = f"{settings.frontend_url}/verify-email?token={token}"
        hours = settings.email_verification_hours
        return verification_email(user.email, user.full_name, link, hours)

    async def resend(self, user: User) -> Email:
        if user.is_email_verified:
            raise AppError("ALREADY_VERIFIED", "Your email is already verified.", 400)
        return await self.create_email(user)

    async def verify(self, token: str) -> User:
        user_id = await self.redis.getdel(f"email_verify:{hash_token(token)}")  # single use
        user = await self.users.get_by_id(uuid.UUID(user_id)) if user_id else None
        if user is None:
            raise AppError(
                "INVALID_VERIFY_LINK",
                "This verification link is invalid or has expired. Log in to get a new one.",
                400,
            )
        await self.redis.delete(f"email_verify_user:{user.id}")
        if not user.is_email_verified:
            user.is_email_verified = True
            await self.session.commit()
            await self.activity.log(self.request, user, "auth.verify_email")
        return user
