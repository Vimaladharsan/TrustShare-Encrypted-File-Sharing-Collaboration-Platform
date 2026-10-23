"""Sharing routes.

Owner:      POST/GET /files/{id}/shares · GET /shares/sent · DELETE /shares/{id} (revoke)
Recipient:  GET /shares/received · GET /shares/{id}/preview|download
Public:     GET /s/{token} · /s/{token}/preview · /s/{token}/download (no login, rate-limited)
"""

import uuid

from fastapi import APIRouter, Depends, Path, Request, status
from fastapi.responses import StreamingResponse
from pymongo.asynchronous.database import AsyncDatabase
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import can_read_files, get_current_user, require_permission
from app.api.routes.files import download_response, preview_response
from app.core.permissions import Perm
from app.core.rate_limit import rate_limit
from app.db.mongo import get_mongo
from app.db.postgres import get_db
from app.models import User
from app.schemas.share import (
    PublicShareInfo,
    ReceivedShareListResponse,
    ShareCreate,
    ShareCreated,
    ShareListResponse,
)
from app.services.share_service import ShareService
from app.storage.secure_store import SecureFileStore, get_file_store

router = APIRouter(tags=["sharing"])
public_router = APIRouter(
    prefix="/s",
    tags=["public share links"],
    dependencies=[Depends(rate_limit("share_link", "share_link_rate_limit_per_minute"))],
)

can_share = require_permission(Perm.SHARE_CREATE)
# Link tokens are 43 URL-safe characters (256 bits); anything else is rejected before any lookup.
Token = Path(..., min_length=20, max_length=100, pattern=r"^[A-Za-z0-9_-]+$")


def share_service(
    request: Request,
    session: AsyncSession = Depends(get_db),
    db: AsyncDatabase = Depends(get_mongo),
    storage: SecureFileStore = Depends(get_file_store),
) -> ShareService:
    return ShareService(session, db, storage, request)


# ---------- owner ----------


@router.post(
    "/files/{file_id}/shares",
    response_model=ShareCreated,
    status_code=status.HTTP_201_CREATED,
    summary="Share a file: secret link or a registered person (requires share:create)",
)
async def create_share(
    file_id: str,
    data: ShareCreate,
    user: User = Depends(can_share),
    service: ShareService = Depends(share_service),
) -> ShareCreated:
    return await service.create(user, file_id, data)


@router.get(
    "/files/{file_id}/shares",
    response_model=ShareListResponse,
    summary="All shares of one of my files, with their status",
)
async def list_file_shares(
    file_id: str,
    user: User = Depends(can_read_files),
    service: ShareService = Depends(share_service),
) -> ShareListResponse:
    return ShareListResponse(items=await service.list_for_file(user, file_id))


@router.get("/shares/sent", response_model=ShareListResponse, summary="Shared by me")
async def list_sent(
    user: User = Depends(can_read_files),
    service: ShareService = Depends(share_service),
) -> ShareListResponse:
    return ShareListResponse(items=await service.list_sent(user))


@router.delete(
    "/shares/{share_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke a share – the link or access stops working immediately",
)
async def revoke_share(
    share_id: uuid.UUID,
    user: User = Depends(get_current_user),  # revoking is always allowed for your own shares
    service: ShareService = Depends(share_service),
) -> None:
    await service.revoke(user, share_id)


# ---------- recipient ----------


@router.get("/shares/received", response_model=ReceivedShareListResponse, summary="Shared with me")
async def list_received(
    user: User = Depends(can_read_files),
    service: ShareService = Depends(share_service),
) -> ReceivedShareListResponse:
    return ReceivedShareListResponse(items=await service.list_received(user))


@router.get("/shares/{share_id}/preview", summary="Preview a file shared with me")
async def preview_received(
    share_id: uuid.UUID,
    user: User = Depends(can_read_files),
    service: ShareService = Depends(share_service),
) -> StreamingResponse:
    return preview_response(*await service.open_direct(user, share_id, "preview"))


@router.get(
    "/shares/{share_id}/download", summary="Download a file shared with me (download permission)"
)
async def download_received(
    share_id: uuid.UUID,
    user: User = Depends(can_read_files),
    service: ShareService = Depends(share_service),
) -> StreamingResponse:
    return download_response(*await service.open_direct(user, share_id, "download"))


# ---------- public links ----------


@public_router.get("/{token}", response_model=PublicShareInfo, summary="Shared file details")
async def link_info(
    token: str = Token, service: ShareService = Depends(share_service)
) -> PublicShareInfo:
    return await service.link_info(token)


@public_router.get("/{token}/preview", summary="View the shared file in the browser")
async def link_preview(
    token: str = Token, service: ShareService = Depends(share_service)
) -> StreamingResponse:
    return preview_response(*await service.open_link(token, "preview"))


@public_router.get("/{token}/download", summary="Download the shared file (download permission)")
async def link_download(
    token: str = Token, service: ShareService = Depends(share_service)
) -> StreamingResponse:
    return download_response(*await service.open_link(token, "download"))
