"""Fill the database with demo accounts, folders and files for the Milestone 1 demo.

    docker compose exec backend python -m app.scripts.seed_demo

Creates a normal User and a Guest (the Admin comes from create_admin), then gives the User
folders and sample files. Files go through the real FileService, so they pass the same checks as
a browser upload and get MongoDB metadata and activity-log entries.

Safe to run again: existing accounts and content are left alone. The password for the demo
accounts is asked for interactively, or read from the SEED_PASSWORD environment variable.
"""

import asyncio
import getpass
import io
import os
import struct
import sys
import zlib

from fastapi import Request, UploadFile
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.permissions import RoleName
from app.core.security import hash_password
from app.db.mongo import close_mongo, ensure_indexes, get_mongo, init_mongo
from app.models import User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import RegisterRequest
from app.services.file_service import FileService
from app.services.folder_service import FolderService
from app.storage.local import get_storage
from app.storage.s3 import get_s3_storage
from app.storage.secure_store import SecureFileStore

DEMO_USERS = [
    ("user@example.com", "Demo User", RoleName.USER),
    ("guest@example.com", "Demo Guest", RoleName.GUEST),
]

# ---------- sample file contents (built in code, so nothing binary is committed) ----------


def sample_pdf(text: str) -> bytes:
    """A tiny valid one-page PDF: numbered objects, a cross-reference table, a trailer."""
    stream = f"BT /F1 24 Tf 72 720 Td ({text}) Tj ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R"
        b" /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")  # the magic bytes our upload check looks for
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(out.tell())
        out.write(b"%d 0 obj\n%s\nendobj\n" % (number, body))
    xref_at = out.tell()
    out.write(b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1))
    for offset in offsets:
        out.write(b"%010d 00000 n \n" % offset)
    out.write(b"trailer\n<< /Size %d /Root 1 0 R >>\n" % (len(objects) + 1))
    out.write(b"startxref\n%d\n%%%%EOF\n" % xref_at)
    return out.getvalue()


def sample_png(width: int = 240, height: int = 160) -> bytes:
    """A blue gradient image. A PNG is a signature followed by IHDR, IDAT and IEND chunks."""

    def chunk(kind: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(kind + data)
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", crc)

    def pixel(x: int, y: int) -> tuple[int, int, int]:
        return 37, 99 + 120 * x // width, 235 - 80 * y // height  # red, green, blue

    # Each row starts with a filter byte (0 = none), then 3 bytes per pixel.
    rows = b"".join(
        b"\x00" + bytes(c for x in range(width) for c in pixel(x, y)) for y in range(height)
    )
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)  # 8-bit RGB
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(rows))
        + chunk(b"IEND", b"")
    )


MEETING_NOTES = """TrustShare – weekly sync
- Milestone 1 demo on Thursday 15 Oct
- Upload, folders and trash are done
- Next: AES-256-GCM encryption and sharing links (Milestone 2)
"""

BUDGET_CSV = """item,quarter,amount_inr
Cloud storage,Q4,12000
Domain and email,Q4,1500
Security audit,Q4,25000
"""

# Folder path → files inside it. "" is the top level ("My Files").
DEMO_CONTENT: dict[str, list[tuple[str, bytes]]] = {
    "": [("Meeting notes.txt", MEETING_NOTES.encode())],
    "Projects": [("Project plan.pdf", sample_pdf("TrustShare project plan"))],
    "Projects/Q4 Report": [
        ("Q4 report.pdf", sample_pdf("Q4 report - confidential")),
        ("Budget.csv", BUDGET_CSV.encode()),
    ],
    "Personal": [("Team photo.png", sample_png())],
}
TRASHED_FILE = ("Old draft.txt", b"An outdated draft - restore me during the demo.\n")

# ---------- accounts (PostgreSQL) ----------


async def create_users(password: str) -> list[User]:
    """Create the demo accounts that don't exist yet. Returns all demo users, in order."""
    settings = get_settings()
    engine = create_async_engine(settings.postgres_url)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            users = UserRepository(session)
            result = []
            for email, full_name, role_name in DEMO_USERS:
                user = await users.get_by_email(email)
                if user is None:
                    # Same name/email/password rules as normal registration.
                    data = RegisterRequest(full_name=full_name, email=email, password=password)
                    user = User(
                        email=data.email,
                        full_name=data.full_name,
                        password_hash=hash_password(data.password),
                        role=await users.get_role(role_name),
                        is_email_verified=True,
                        storage_quota_bytes=settings.default_quota_mb * 1024 * 1024,
                    )
                    await users.add(user)
                    print(f"Created {role_name} account {email}")
                else:
                    print(f"{email} already exists – left unchanged")
                result.append(user)
            await session.commit()
            return result
    finally:
        await engine.dispose()


# ---------- folders and files (MongoDB + storage) ----------


def script_request() -> Request:
    """The services log who did what and from where; here the "request" is this script."""
    scope = {
        "type": "http",
        "headers": [(b"user-agent", b"seed-demo-script")],
        "client": ("127.0.0.1", 0),
    }
    return Request(scope)


async def add_demo_content(user: User) -> None:
    db = get_mongo()
    if await db["files"].count_documents({"owner_id": str(user.id)}, limit=1):
        print(f"{user.email} already has files – content not added")
        return

    request = script_request()
    folders = FolderService(db, request)
    await asyncio.to_thread(get_s3_storage().ensure_bucket)
    engine = create_async_engine(get_settings().postgres_url)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            # Files are encrypted and stored exactly like a browser upload.
            store = SecureFileStore(session, get_s3_storage(), get_storage())
            files = FileService(db, store, request)
            await _add_folders_and_files(user, folders, files)
    finally:
        await engine.dispose()
    print(f"Added {len(DEMO_CONTENT) - 1} folders and sample files for {user.email}")


async def _add_folders_and_files(user: User, folders: FolderService, files: FileService) -> None:
    async def upload(name: str, content: bytes, folder_id: str | None) -> dict:
        upload_file = UploadFile(io.BytesIO(content), filename=name)
        return await files.upload(user, upload_file, folder_id, allow_duplicate=False)

    # Parents come before their sub-folders in DEMO_CONTENT, so their IDs are already known.
    folder_ids: dict[str, str | None] = {"": None}
    for path, items in DEMO_CONTENT.items():
        if path:
            parent, _, name = path.rpartition("/")
            folder = await folders.create(user, name, folder_ids[parent])
            folder_ids[path] = str(folder["_id"])
        for name, content in items:
            await upload(name, content, folder_ids[path])

    draft = await upload(*TRASHED_FILE, folder_id=None)
    await files.trash(user, str(draft["_id"]))


# ---------- entry point ----------


async def seed(password: str) -> None:
    demo_users = await create_users(password)
    init_mongo(get_settings())
    try:
        await ensure_indexes()
        await add_demo_content(demo_users[0])  # the User; Guests can't upload
    finally:
        await close_mongo()


def main() -> None:
    password = os.environ.get("SEED_PASSWORD") or getpass.getpass("Demo account password: ")
    try:
        asyncio.run(seed(password))
    except ValidationError as exc:
        sys.exit("Invalid input: " + "; ".join(err["msg"] for err in exc.errors()))
    print("Done. Log in as user@example.com or guest@example.com with that password.")


if __name__ == "__main__":
    main()
