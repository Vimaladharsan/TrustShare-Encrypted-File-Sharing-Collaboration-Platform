"""Create the first Admin, or promote an existing user to Admin.

Nobody can sign up as Admin through the API, so the first one is made from the command line:

    docker compose exec backend python -m app.scripts.create_admin \
        --email admin@example.com --name "Admin"

The password is asked for interactively (hidden, and not saved in the shell history).
"""

import argparse
import asyncio
import getpass
import sys

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.permissions import RoleName
from app.core.security import hash_password
from app.models import User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import RegisterRequest


async def user_exists(email: str) -> bool:
    engine = create_async_engine(get_settings().postgres_url)
    try:
        async with async_sessionmaker(engine)() as session:
            return await UserRepository(session).get_by_email(email) is not None
    finally:
        await engine.dispose()


async def make_admin(email: str, full_name: str, password: str | None = None) -> str:
    """Promote the user with this email, or create a new Admin. Returns what was done."""
    settings = get_settings()
    engine = create_async_engine(settings.postgres_url)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            users = UserRepository(session)
            admin_role = await users.get_role(RoleName.ADMIN)
            user = await users.get_by_email(email)
            if user is not None:
                user.role = admin_role
                action = "promoted to admin"
            else:
                if not password:
                    raise ValueError("A password is required to create a new user")
                # Same name/email/password rules as normal registration.
                data = RegisterRequest(full_name=full_name, email=email, password=password)
                user = User(
                    email=data.email,
                    full_name=data.full_name,
                    password_hash=hash_password(data.password),
                    role=admin_role,
                    is_email_verified=True,
                    storage_quota_bytes=settings.default_quota_mb * 1024 * 1024,
                )
                await users.add(user)
                action = "created as admin"
            await session.commit()
            return action
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Create or promote a TrustShare admin.")
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", default="Administrator")
    args = parser.parse_args()

    password = None
    if not asyncio.run(user_exists(args.email)):
        password = getpass.getpass("New admin password: ")
        if password != getpass.getpass("Repeat password: "):
            sys.exit("Passwords do not match.")

    try:
        action = asyncio.run(make_admin(args.email, args.name, password))
    except ValidationError as exc:
        sys.exit("Invalid input: " + "; ".join(err["msg"] for err in exc.errors()))
    print(f"{args.email}: {action}")


if __name__ == "__main__":
    main()
