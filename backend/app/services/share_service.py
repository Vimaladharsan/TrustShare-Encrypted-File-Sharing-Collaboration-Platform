"""Sharing: secure links and direct shares with registered users. All sharing rules live here.

Creating (owner only, needs share:create):
  link  → 256-bit random token; only its SHA-256 is stored; the link is shown once
  user  → the recipient must be an active account; it appears in their "Shared with Me"

Every access re-checks everything (docs/architecture.md §8.4):
  share exists → not revoked → not expired → downloads left → owner still active and still
  allowed to share → file still active → action allowed by the permission
  ("view" = preview only, "download" = preview + download)
Only then is the file decrypted (SecureFileStore). Trashing the file, disabling the owner or
taking away their share:create permission stops every link at once – no clean-up needed.
Admins get no special access here (privacy).
"""

import hashlib
import secrets
import uuid
from collections.abc import AsyncIterator, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from urllib.parse import unquote

from fastapi import Request
from pymongo.asynchronous.database import AsyncDatabase
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.permissions import Perm
from app.core.rate_limit import client_ip
from app.core.security import hash_password, verify_password
from app.core.user_agent import describe_device
from app.db.redis import get_redis
from app.models import Share, User
from app.repositories.file_repository import FileRepository
from app.repositories.folder_repository import FolderRepository
from app.repositories.share_repository import ShareRepository
from app.repositories.user_repository import UserRepository
from app.schemas.share import (
    BulkShareFailure,
    BulkShareResult,
    PublicShareInfo,
    ReceivedShare,
    ShareAccessEvent,
    ShareAccessHistory,
    ShareAccessSummary,
    ShareBulkCreate,
    ShareCreate,
    ShareCreated,
    ShareInfo,
    ShareStatus,
    ShareUpdate,
)
from app.services.activity_service import ActivityService
from app.services.email_service import Email, file_shared_email
from app.services.file_validation import PREVIEWABLE
from app.services.security_events import record_security_event
from app.storage.secure_store import SecureFileStore

Action = Literal["info", "preview", "download"]

# Access history: activity → what the owner sees. Refusal codes in plain words.
ACCESS_EVENTS = {
    "share.link_opened": "opened",
    "file.preview": "viewed",
    "file.download": "downloaded",
    "share.access_denied": "refused",
}
REFUSAL_TEXT = {
    "SHARE_EXPIRED": "link expired",
    "SHARE_REVOKED": "share revoked",
    "SHARE_LIMIT_REACHED": "download limit reached",
    "SHARE_DOWNLOAD_NOT_ALLOWED": "download not allowed (view only)",
    "SHARE_NOT_FOUND": "file no longer available",
    "SHARE_PASSWORD_INVALID": "wrong password",
    "SHARE_PASSWORD_LOCKED": "too many wrong passwords",
}
# Header name, not a secret. URL-encoded, so any characters work in a header.
PASSWORD_HEADER = "X-Share-Password"  # noqa: S105
PASSWORD_MAX_TRIES = 5  # wrong passwords per link and visitor IP …
PASSWORD_LOCK_SECONDS = 15 * 60  # … then that visitor is locked out of the link for 15 minutes
FOLDER_SHARE_MAX_FILES = 50
LINK_OPEN_THROTTLE_SECONDS = 300  # a reload within 5 minutes isn't a new visit


def mask_ip(ip: str | None) -> str | None:
    """203.0.113.42 → 203.0.113.x; IPv6 keeps its first four groups. Owners see roughly where a
    visit came from, not the visitor's exact address."""
    if not ip or ip in {"testclient", "unknown"}:
        return ip
    if "." in ip and ":" not in ip:
        return ".".join(ip.split(".")[:3] + ["x"])
    return ":".join(ip.split(":")[:4]) + ":…"


DOWNLOAD_ANOMALY_THRESHOLD = 20


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def share_status(share: Share, now: datetime | None = None) -> ShareStatus:
    """The share's own state (file and owner checks come on top when it is used)."""
    now = now or datetime.now(UTC)
    if share.revoked_at:
        return "revoked"
    if share.expires_at and share.expires_at <= now:
        return "expired"
    if share.max_downloads is not None and share.download_count >= share.max_downloads:
        return "used_up"
    return "active"


def _file_not_found() -> AppError:
    return AppError("FILE_NOT_FOUND", "File not found.", 404)


def _share_not_found() -> AppError:
    # Same answer for "never existed", "not yours" and "file/owner gone": reveal nothing.
    return AppError("SHARE_NOT_FOUND", "This share link is invalid or no longer available.", 404)


STATUS_ERRORS = {
    "revoked": ("SHARE_REVOKED", "The owner has revoked this share."),
    "expired": ("SHARE_EXPIRED", "This share has expired."),
    "used_up": ("SHARE_LIMIT_REACHED", "This share has reached its download limit."),
}


class ShareService:
    def __init__(
        self,
        session: AsyncSession,
        db: AsyncDatabase,
        storage: SecureFileStore,
        request: Request,
    ) -> None:
        self.session = session
        self.shares = ShareRepository(session)
        self.users = UserRepository(session)
        self.files = FileRepository(db)
        self.folders = FolderRepository(db)
        self.db = db
        self.activity = ActivityService(db)
        self.storage = storage
        self.request = request

    # ---------- owner: create, list, revoke ----------

    async def create(
        self,
        owner: User,
        file_id: str,
        data: ShareCreate,
        batch: bool = False,
        password_hash: str | None = None,  # already hashed (a batch hashes the password once)
    ) -> ShareCreated:
        file = await self._owned_active_file(owner, file_id)
        if data.permission == "view" and file["extension"] not in PREVIEWABLE:
            raise AppError(
                "VIEW_NOT_SUPPORTED",
                f".{file['extension']} files can't be previewed in the browser, so share them "
                "with download permission.",
                400,
            )
        now = datetime.now(UTC)
        expires_at = data.expires_at
        if expires_at is not None and expires_at <= now:
            raise AppError("INVALID_EXPIRY", "The expiry time must be in the future.", 400)

        token: str | None = None
        recipient: User | None = None
        if data.share_type == "link":
            max_days = get_settings().share_link_max_days
            if expires_at is None or expires_at > now + timedelta(days=max_days, minutes=5):
                raise AppError(
                    "INVALID_EXPIRY",
                    f"Share links must expire within {max_days} days.",
                    400,
                )
            token = secrets.token_urlsafe(32)  # 256 bits of randomness
        else:
            recipient = await self._recipient(owner, str(data.recipient_email))
            await self._close_old_direct_share(file_id, recipient)

        share = Share(
            file_id=file_id,
            owner_id=owner.id,
            share_type=data.share_type,
            recipient_id=recipient.id if recipient else None,
            token_hash=hash_token(token) if token else None,
            permission=data.permission,
            expires_at=expires_at,
            max_downloads=data.max_downloads,
            download_count=0,
            password_hash=password_hash
            or (hash_password(data.password) if data.password else None),
        )
        try:
            await self.shares.add(share)
            await self.session.commit()
        except IntegrityError as exc:  # two identical requests at the same moment
            await self.session.rollback()
            raise self._already_shared() from exc
        await self.session.refresh(share)

        await self.activity.log(
            self.request,
            owner,
            "share.create",
            resource_type="file",
            resource_id=file_id,
            details={
                "share_id": str(share.id),
                "share_type": share.share_type,
                "permission": share.permission,
                "file_name": file["original_name"],
                "recipient_email": recipient.email if recipient else None,
                "recipient_id": str(recipient.id) if recipient else None,
                "expires_at": expires_at.isoformat() if expires_at else None,
                "max_downloads": share.max_downloads,
                "password_protected": share.password_hash is not None,
                # part of a "share several files" request: the recipient is told once, below
                "batch": batch,
            },
        )
        info = self._info(share, file, recipient)
        url = f"{get_settings().frontend_url}/s/{token}" if token else None
        return ShareCreated(**info.model_dump(), url=url)

    async def create_many(
        self, owner: User, data: ShareBulkCreate, folder_name: str | None = None
    ) -> BulkShareResult:
        """The same share for several files. Each file is checked on its own (one problem doesn't
        stop the rest); a person gets ONE notification and email for the whole batch."""
        password_hash = hash_password(data.password) if data.password else None
        recipient = None
        if data.share_type == "user":  # an unknown person stops the whole request at once
            recipient = await self._recipient(owner, str(data.recipient_email))
        single = ShareCreate(**data.model_dump(exclude={"file_ids"}))
        created: list[ShareCreated] = []
        failed: list[BulkShareFailure] = []
        for file_id in dict.fromkeys(data.file_ids):
            try:
                created.append(
                    await self.create(
                        owner, file_id, single, batch=True, password_hash=password_hash
                    )
                )
            except AppError as exc:
                failed.append(BulkShareFailure(file_id=file_id, code=exc.code, message=exc.message))
        if recipient is not None and created:
            await self.activity.log(
                self.request,
                owner,
                "share.create_batch",
                details={
                    "share_type": "user",
                    "permission": data.permission,
                    "count": len(created),
                    "file_names": [share.file_name for share in created][:20],
                    "recipient_email": recipient.email,
                    "recipient_id": str(recipient.id),
                    "expires_at": data.expires_at.isoformat() if data.expires_at else None,
                    "folder_name": folder_name,
                },
            )
        return BulkShareResult(created=created, failed=failed)

    async def share_folder(self, owner: User, folder_id: str, data: ShareCreate) -> BulkShareResult:
        """Share every file in one of my folders (sub-folders included) with the same settings.
        The files in the folder now are shared – files added later are not included."""
        folder = await self.folders.get_active_owned(str(owner.id), folder_id)
        if folder is None:
            raise AppError("FOLDER_NOT_FOUND", "Folder not found.", 404)
        folder_ids = [folder["_id"]] + [
            sub["_id"]
            for sub in await self.folders.descendants(folder["_id"])
            if sub.get("status") == "active"
        ]
        files = (
            await self.db["files"]
            .find(
                {"owner_id": str(owner.id), "status": "active", "folder_id": {"$in": folder_ids}},
                {"_id": 1},
            )
            .sort("name_lower", 1)
            .to_list(length=FOLDER_SHARE_MAX_FILES + 1)
        )
        if not files:
            raise AppError("FOLDER_EMPTY", "This folder has no files to share.", 400)
        if len(files) > FOLDER_SHARE_MAX_FILES:
            raise AppError(
                "FOLDER_TOO_LARGE",
                f"A folder can be shared with up to {FOLDER_SHARE_MAX_FILES} files at once.",
                400,
            )
        bulk = ShareBulkCreate(**data.model_dump(), file_ids=[str(f["_id"]) for f in files])
        return await self.create_many(owner, bulk, folder_name=folder["name"])

    async def list_for_file(self, owner: User, file_id: str) -> list[ShareInfo]:
        file = await self.files.get(file_id)
        if file is None or file["owner_id"] != str(owner.id):
            raise _file_not_found()
        return await self._infos(await self.shares.for_file(file_id))

    async def list_sent(self, owner: User) -> list[ShareInfo]:
        return await self._infos(await self.shares.sent_by(owner.id))

    async def revoke(self, owner: User, share_id: uuid.UUID) -> None:
        share = await self.shares.get(share_id)
        if share is None or share.owner_id != owner.id:
            raise _share_not_found()
        if share.revoked_at is not None:
            return  # already revoked – nothing to do
        share.revoked_at = datetime.now(UTC)
        await self.session.commit()
        await self.activity.log(
            self.request,
            owner,
            "share.revoke",
            resource_type="file",
            resource_id=share.file_id,
            details={"share_id": str(share.id), "share_type": share.share_type},
        )

    async def update(self, owner: User, share_id: uuid.UUID, data: ShareUpdate) -> ShareInfo:
        """Change permission, expiry and/or download limit of one of my shares (same link)."""
        share = await self.shares.get(share_id)
        if share is None or share.owner_id != owner.id:
            raise _share_not_found()
        if share.revoked_at is not None:
            raise AppError(
                "SHARE_REVOKED", "A revoked share can't be changed – create a new one.", 409
            )
        file = await self._owned_active_file(owner, share.file_id)
        sent = data.model_fields_set
        now = datetime.now(UTC)
        before = (share.permission, share.expires_at, share.max_downloads)

        permission = data.permission if "permission" in sent else share.permission
        if permission == "view" and file["extension"] not in PREVIEWABLE:
            raise AppError(
                "VIEW_NOT_SUPPORTED",
                f".{file['extension']} files can't be previewed in the browser, so they need "
                "download permission.",
                400,
            )
        expires_at = data.expires_at if "expires_at" in sent else share.expires_at
        if "expires_at" in sent:
            if expires_at is not None and expires_at <= now:
                raise AppError("INVALID_EXPIRY", "The expiry time must be in the future.", 400)
            max_days = get_settings().share_link_max_days
            if share.share_type == "link" and (
                expires_at is None or expires_at > now + timedelta(days=max_days, minutes=5)
            ):
                raise AppError(
                    "INVALID_EXPIRY", f"Share links must expire within {max_days} days.", 400
                )
        max_downloads = data.max_downloads if "max_downloads" in sent else share.max_downloads
        if permission == "view":
            max_downloads = None  # a download limit means nothing without download permission
        if max_downloads is not None and max_downloads < share.download_count:
            raise AppError(
                "INVALID_LIMIT",
                f"The file was already downloaded {share.download_count} times – the limit "
                "can't be lower than that.",
                400,
            )

        changes = [
            name
            for name, old, new in zip(
                ("permission", "expiry", "download limit"),
                before,
                (permission, expires_at, max_downloads),
                strict=True,
            )
            if old != new
        ]
        if "password" in sent:
            if share.share_type != "link":
                raise AppError(
                    "PASSWORD_ONLY_FOR_LINKS", "A password can only be set for share links.", 400
                )
            share.password_hash = hash_password(data.password) if data.password else None
            changes.append("password" if data.password else "password removed")
        recipient = await self._recipient_of(share)
        if not changes:
            return self._info(share, file, recipient)
        share.permission = permission
        share.expires_at = expires_at
        share.max_downloads = max_downloads
        if "expiry" in changes:
            # New expiry → the owner gets a fresh reminder and the expiry is recorded again.
            share.reminder_sent_at = None
            share.expiry_recorded_at = None
        await self.session.commit()
        await self.session.refresh(share)

        await self.activity.log(
            self.request,
            owner,
            "share.update",
            resource_type="file",
            resource_id=share.file_id,
            details={
                "share_id": str(share.id),
                "share_type": share.share_type,
                "changes": ", ".join(changes),
                "permission": share.permission,
                "file_name": file["original_name"],
                "recipient_id": str(recipient.id) if recipient else None,
                "expires_at": expires_at.isoformat() if expires_at else None,
                "max_downloads": max_downloads,
            },
        )
        return self._info(share, file, recipient)

    async def access_history(self, owner: User, share_id: uuid.UUID) -> ShareAccessHistory:
        """Who opened, viewed or downloaded one of my shares, when and from which device –
        including refused attempts (expired, revoked, limit reached …)."""
        share = await self.shares.get(share_id)
        if share is None or share.owner_id != owner.id:
            raise _share_not_found()
        entries = (
            await self.activity.logs.find(
                {"details.share_id": str(share.id), "action": {"$in": list(ACCESS_EVENTS)}}
            )
            .sort("created_at", -1)
            .limit(200)
            .to_list(length=200)
        )
        names: dict[str, str] = {}  # registered visitors (direct shares, signed-in link visitors)
        for user_id in {e["user_id"] for e in entries if e.get("user_id")}:
            person = await self.users.get_by_id(uuid.UUID(user_id))
            if person is not None:
                names[user_id] = person.full_name
        items: list[ShareAccessEvent] = []
        visitors: set[str] = set()
        for entry in entries:
            device = describe_device(entry.get("user_agent", ""))
            email = entry.get("actor_email")
            name = names.get(entry.get("user_id") or "")
            visitors.add(email or f"{entry.get('ip_address')}|{entry.get('user_agent')}")
            event = ACCESS_EVENTS[entry["action"]]
            reason = (entry.get("details") or {}).get("reason")
            items.append(
                ShareAccessEvent(
                    at=entry["created_at"],
                    event=event,
                    detail=REFUSAL_TEXT.get(reason, reason) if event == "refused" else None,
                    visitor=name or email or "Anonymous visitor",
                    visitor_email=email,
                    device=f"{device['browser']} on {device['os']}",
                    kind=device["kind"],
                    ip=mask_ip(entry.get("ip_address")),
                )
            )
        counts = {kind: sum(1 for i in items if i.event == kind) for kind in ACCESS_EVENTS.values()}
        return ShareAccessHistory(
            share_id=share.id,
            summary=ShareAccessSummary(**counts, visitors=len(visitors)),
            items=items,
        )

    async def _recipient_of(self, share: Share) -> User | None:
        return await self.users.get_by_id(share.recipient_id) if share.recipient_id else None

    # ---------- recipient: "Shared with Me" ----------

    async def list_received(self, user: User) -> list[ReceivedShare]:
        items: list[ReceivedShare] = []
        owners: dict[uuid.UUID, User | None] = {}
        for share in await self.shares.received_by(user.id):
            if share_status(share) != "active":
                continue
            if share.owner_id not in owners:
                owners[share.owner_id] = await self.users.get_by_id(share.owner_id)
            owner = owners[share.owner_id]
            file = await self.files.get(share.file_id)
            if not _owner_can_share(owner) or not _file_usable(file, share):
                continue
            items.append(
                ReceivedShare(
                    id=share.id,
                    file_id=share.file_id,
                    file_name=file["original_name"],
                    extension=file["extension"],
                    mime_type=file["mime_type"],
                    category=file["category"],
                    size_bytes=file["size_bytes"],
                    permission=share.permission,
                    owner_name=owner.full_name,
                    owner_email=owner.email,
                    expires_at=share.expires_at,
                    shared_at=share.created_at,
                    can_preview=file["extension"] in PREVIEWABLE,
                )
            )
        return items

    async def open_direct(
        self, user: User, share_id: uuid.UUID, action: Action
    ) -> tuple[dict[str, Any], AsyncIterator[bytes]]:
        share = await self.shares.get(share_id)
        if share is None or share.recipient_id != user.id:
            await self._denied(user, "SHARE_NOT_FOUND", share_id=share_id)
            raise _share_not_found()
        return await self._open(share, action, visitor=user)

    # ---------- link visitors (no account) ----------

    async def link_info(self, token: str) -> PublicShareInfo:
        share, file, owner = await self._resolve_link(token, "info")
        await self._check_password(share)
        await self._record_link_open(share)
        downloads_left = (
            share.max_downloads - share.download_count if share.max_downloads is not None else None
        )
        return PublicShareInfo(
            file_name=file["original_name"],
            extension=file["extension"],
            mime_type=file["mime_type"],
            category=file["category"],
            size_bytes=file["size_bytes"],
            permission=share.permission,
            owner_name=owner.full_name,
            expires_at=share.expires_at,
            downloads_left=downloads_left,
            can_preview=file["extension"] in PREVIEWABLE,
        )

    async def _record_link_open(self, share: Share) -> None:
        """Someone opened the link page – once per visitor (IP + browser) per 5 minutes."""
        ip = client_ip(self.request)
        agent = hashlib.sha256(self.request.headers.get("user-agent", "").encode()).hexdigest()[:16]
        key = f"link_open:{share.id}:{ip}:{agent}"
        if not await get_redis().set(key, "1", nx=True, ex=LINK_OPEN_THROTTLE_SECONDS):
            return
        await self.activity.log(
            self.request,
            None,
            "share.link_opened",
            resource_type="file",
            resource_id=share.file_id,
            details={"share_id": str(share.id), "owner_id": str(share.owner_id)},
        )

    async def open_link(
        self, token: str, action: Action
    ) -> tuple[dict[str, Any], AsyncIterator[bytes]]:
        share = await self.shares.by_token_hash(hash_token(token))
        if share is None:
            await self._invalid_link()
            raise _share_not_found()
        await self._check_password(share)
        return await self._open(share, action, visitor=None)

    async def _check_password(self, share: Share) -> None:
        """Links with a password: the visitor sends it in the X-Share-Password header. 403 (not
        401, which the web app treats as "signed out") when it is missing or wrong; 5 wrong tries
        lock that visitor out of the link for 15 minutes."""
        if share.password_hash is None:
            return
        redis = get_redis()
        key = f"share_pw_fail:{share.id}:{client_ip(self.request)}"
        if int(await redis.get(key) or 0) >= PASSWORD_MAX_TRIES:
            await self._denied(None, "SHARE_PASSWORD_LOCKED", share=share)
            raise AppError(
                "SHARE_PASSWORD_LOCKED",
                "Too many wrong passwords. Try again in 15 minutes.",
                429,
            )
        typed = unquote(self.request.headers.get(PASSWORD_HEADER, ""))
        if not typed:
            raise AppError(
                "SHARE_PASSWORD_REQUIRED", "This link is protected with a password.", 403
            )
        if not verify_password(typed, share.password_hash):
            await redis.incr(key)
            await redis.expire(key, PASSWORD_LOCK_SECONDS)
            await self._denied(None, "SHARE_PASSWORD_INVALID", share=share)
            raise AppError("SHARE_PASSWORD_INVALID", "Wrong password.", 403)
        await redis.delete(key)

    # ---------- the checks ----------

    async def _resolve_link(self, token: str, action: Action) -> tuple[Share, dict, User]:
        share = await self.shares.by_token_hash(hash_token(token))
        if share is None:
            await self._invalid_link()
            raise _share_not_found()
        file, owner = await self._check(share, action, visitor=None)
        return share, file, owner

    async def _check(
        self, share: Share, action: Action, visitor: User | None
    ) -> tuple[dict[str, Any], User]:
        """All access rules for one use of a share. Raises AppError (and logs) on any failure."""
        status = share_status(share)
        if status != "active":
            code, message = STATUS_ERRORS[status]
            await self._denied(visitor, code, share=share)
            raise AppError(code, message, 410)

        owner = await self.users.get_by_id(share.owner_id)
        file = await self.files.get(share.file_id)
        if not _owner_can_share(owner) or not _file_usable(file, share):
            await self._denied(visitor, "SHARE_NOT_FOUND", share=share)
            raise _share_not_found()

        if action == "download" and share.permission != "download":
            await self._denied(visitor, "SHARE_DOWNLOAD_NOT_ALLOWED", share=share)
            raise AppError(
                "SHARE_DOWNLOAD_NOT_ALLOWED",
                "The owner only allowed viewing this file, not downloading it.",
                403,
            )
        if action == "preview" and file["extension"] not in PREVIEWABLE:
            raise AppError(
                "PREVIEW_NOT_SUPPORTED", "This file type can't be previewed. Download it.", 415
            )
        return file, owner

    async def _open(
        self, share: Share, action: Action, visitor: User | None
    ) -> tuple[dict[str, Any], AsyncIterator[bytes]]:
        file, _ = await self._check(share, action, visitor)
        if action == "download":
            if not await self.shares.claim_download(share.id):  # last one taken meanwhile
                code, message = STATUS_ERRORS["used_up"]
                await self._denied(visitor, code, share=share)
                raise AppError(code, message, 410)
        else:
            await self.shares.touch(share.id)
        await self.session.commit()

        chunks = await self.storage.open(file)  # decrypt + verify (raises before sending)
        if action == "download" and share.share_type == "link":
            await self._watch_downloads(share)
        await self.activity.log(
            self.request,
            visitor,
            f"file.{action}",
            resource_type="file",
            resource_id=share.file_id,
            details={
                "file_name": file["original_name"],
                "via": "link" if share.share_type == "link" else "direct_share",
                "share_id": str(share.id),
                "owner_id": str(share.owner_id),
            },
        )
        return file, chunks

    async def _denied(
        self,
        visitor: User | None,
        reason: str,
        share: Share | None = None,
        share_id: uuid.UUID | None = None,
    ) -> None:
        """Failed share access – recorded for the security dashboard (Phase 8)."""
        share_ref = share.id if share else share_id
        await self.activity.log(
            self.request,
            visitor,
            "share.access_denied",
            resource_type="file" if share else None,
            resource_id=share.file_id if share else None,
            status="failure",
            details={"reason": reason, "share_id": str(share_ref) if share_ref else None},
        )

    async def _invalid_link(self) -> None:
        await self._denied(None, "SHARE_NOT_FOUND")
        await record_security_event(
            "unauthorized_access",
            request=self.request,
            severity="low",
            message="Invalid share link used",
        )

    async def _watch_downloads(self, share: Share) -> None:
        """Many downloads through one link from one IP in 10 minutes looks like scraping."""
        ip = client_ip(self.request)
        recent = await self.activity.logs.count_documents(
            {
                "action": "file.download",
                "details.share_id": str(share.id),
                "ip_address": ip,
                "created_at": {"$gte": datetime.now(UTC) - timedelta(minutes=10)},
            }
        )
        if recent + 1 == DOWNLOAD_ANOMALY_THRESHOLD:  # this download is not logged yet
            await record_security_event(
                "download_anomaly",
                request=self.request,
                details={"share_id": str(share.id), "downloads_10min": recent + 1},
            )

    # ---------- helpers ----------

    async def _owned_active_file(self, owner: User, file_id: str) -> dict[str, Any]:
        file = await self.files.get(file_id)
        if file is None or file["owner_id"] != str(owner.id) or file["status"] != "active":
            raise _file_not_found()
        return file

    async def _recipient(self, owner: User, email: str) -> User:
        recipient = await self.users.get_by_email(email)
        if recipient is None or not recipient.is_active:
            raise AppError(
                "RECIPIENT_NOT_FOUND", "No active TrustShare account uses this email.", 404
            )
        if recipient.id == owner.id:
            raise AppError("CANNOT_SHARE_WITH_SELF", "You can't share a file with yourself.", 400)
        return recipient

    async def _close_old_direct_share(self, file_id: str, recipient: User) -> None:
        """One open direct share per person and file: an expired or used-up one is closed so a
        new one can replace it; a still-working one is an error."""
        existing = await self.shares.open_direct_share(file_id, recipient.id)
        if existing is None:
            return
        if share_status(existing) == "active":
            raise self._already_shared()
        existing.revoked_at = datetime.now(UTC)
        await self.session.flush()

    @staticmethod
    def _already_shared() -> AppError:
        return AppError(
            "ALREADY_SHARED",
            "This file is already shared with that person. Revoke the share to change it.",
            409,
        )

    async def _infos(self, shares: Sequence[Share]) -> list[ShareInfo]:
        files: dict[str, dict[str, Any] | None] = {}
        people: dict[uuid.UUID, User | None] = {}
        result = []
        for share in shares:
            if share.file_id not in files:
                files[share.file_id] = await self.files.get(share.file_id)
            recipient = None
            if share.recipient_id:
                if share.recipient_id not in people:
                    people[share.recipient_id] = await self.users.get_by_id(share.recipient_id)
                recipient = people[share.recipient_id]
            result.append(self._info(share, files[share.file_id], recipient))
        return result

    @staticmethod
    def _info(share: Share, file: dict[str, Any] | None, recipient: User | None) -> ShareInfo:
        status = share_status(share)
        if status == "active" and (file is None or file["status"] != "active"):
            status = "file_unavailable"
        return ShareInfo(
            id=share.id,
            file_id=share.file_id,
            file_name=file["original_name"] if file else None,
            share_type=share.share_type,
            permission=share.permission,
            recipient_email=recipient.email if recipient else None,
            recipient_name=recipient.full_name if recipient else None,
            expires_at=share.expires_at,
            max_downloads=share.max_downloads,
            download_count=share.download_count,
            has_password=share.password_hash is not None,
            status=status,
            created_at=share.created_at,
            last_accessed_at=share.last_accessed_at,
        )


def _owner_can_share(owner: User | None) -> bool:
    """A link works only while its creator is active and still allowed to share."""
    return owner is not None and owner.is_active and Perm.SHARE_CREATE in owner.permission_codes


def _file_usable(file: dict[str, Any] | None, share: Share) -> bool:
    return (
        file is not None and file["status"] == "active" and file["owner_id"] == str(share.owner_id)
    )


def direct_share_email(owner: User, share: ShareCreated) -> Email:
    """The "shared with you" notification for a direct share."""
    expires = share.expires_at.strftime("%d %b %Y, %H:%M UTC") if share.expires_at else None
    return file_shared_email(
        to=share.recipient_email or "",
        name=share.recipient_name or "",
        owner_name=owner.full_name,
        owner_email=owner.email,
        file_name=share.file_name or "a file",
        can_download=share.permission == "download",
        expires=expires,
        link=f"{get_settings().frontend_url}/shared-with-me",
    )
