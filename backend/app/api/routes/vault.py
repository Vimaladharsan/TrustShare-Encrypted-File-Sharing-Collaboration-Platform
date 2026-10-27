"""Secure vault (/api/vault). Every file request carries the vault password in the
X-Vault-Password header (URL-encoded, so any characters work). Nothing stays unlocked between
requests. Rules and cryptography: app/services/vault_service.py, app/crypto/vault_crypto.py.
"""

from urllib.parse import unquote

from fastapi import APIRouter, Depends, File, Header, Request, UploadFile, status
from fastapi.responses import StreamingResponse
from pymongo.asynchronous.database import AsyncDatabase
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import can_upload_files, get_current_user
from app.api.routes.files import download_response, preview_response
from app.db.mongo import get_mongo
from app.db.postgres import get_db
from app.db.redis import get_redis
from app.models import User
from app.schemas.file import FileInfo
from app.schemas.vault import (
    VaultCreate,
    VaultFile,
    VaultFileList,
    VaultPasswordChange,
    VaultRename,
    VaultReset,
    VaultStatus,
)
from app.services.vault_service import VaultService
from app.storage.secure_store import SecureFileStore, get_file_store

router = APIRouter(prefix="/vault", tags=["vault"])


def vault_service(
    request: Request,
    session: AsyncSession = Depends(get_db),
    db: AsyncDatabase = Depends(get_mongo),
    redis: Redis = Depends(get_redis),
    storage: SecureFileStore = Depends(get_file_store),
) -> VaultService:
    return VaultService(session, db, redis, storage, request)


def vault_password(
    x_vault_password: str = Header(..., max_length=512, description="URL-encoded vault password"),
) -> str:
    return unquote(x_vault_password)


@router.get("", response_model=VaultStatus, summary="Does my vault exist, and is it locked?")
async def get_status(
    user: User = Depends(get_current_user), service: VaultService = Depends(vault_service)
) -> VaultStatus:
    return await service.status(user)


@router.post("", status_code=status.HTTP_201_CREATED, summary="Create my vault with a password")
async def create_vault(
    data: VaultCreate,
    user: User = Depends(can_upload_files),
    service: VaultService = Depends(vault_service),
) -> dict[str, str]:
    await service.create(user, data.password)
    return {"status": "created"}


@router.post("/password", status_code=status.HTTP_204_NO_CONTENT, summary="Change vault password")
async def change_password(
    data: VaultPasswordChange,
    user: User = Depends(can_upload_files),
    service: VaultService = Depends(vault_service),
) -> None:
    await service.change_password(user, data)


@router.post("/reset", summary="Forgot the vault password: delete the vault and all its files")
async def reset_vault(
    data: VaultReset,
    user: User = Depends(can_upload_files),
    service: VaultService = Depends(vault_service),
) -> dict[str, int]:
    return {"files_deleted": await service.reset(user, data)}


@router.get("/files", response_model=VaultFileList, summary="List my vault files")
async def list_files(
    user: User = Depends(can_upload_files),
    password: str = Depends(vault_password),
    service: VaultService = Depends(vault_service),
) -> VaultFileList:
    return VaultFileList(items=await service.list(user, password))


@router.post(
    "/files",
    response_model=VaultFile,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a file straight into the vault",
)
async def upload_file(
    file: UploadFile = File(...),
    user: User = Depends(can_upload_files),
    password: str = Depends(vault_password),
    service: VaultService = Depends(vault_service),
) -> VaultFile:
    return await service.upload(user, file, password)


@router.get("/files/{file_id}/preview", summary="Show a vault file in the browser")
async def preview_file(
    file_id: str,
    user: User = Depends(can_upload_files),
    password: str = Depends(vault_password),
    service: VaultService = Depends(vault_service),
) -> StreamingResponse:
    doc, chunks = await service.open(user, file_id, password, preview=True)
    return preview_response(doc, chunks)


@router.get("/files/{file_id}/download", summary="Download a vault file")
async def download_file(
    file_id: str,
    user: User = Depends(can_upload_files),
    password: str = Depends(vault_password),
    service: VaultService = Depends(vault_service),
) -> StreamingResponse:
    doc, chunks = await service.open(user, file_id, password, preview=False)
    return download_response(doc, chunks)


@router.patch("/files/{file_id}", response_model=VaultFile, summary="Rename a vault file")
async def rename_file(
    file_id: str,
    data: VaultRename,
    user: User = Depends(can_upload_files),
    password: str = Depends(vault_password),
    service: VaultService = Depends(vault_service),
) -> VaultFile:
    return await service.rename(user, file_id, password, data.name)


@router.delete(
    "/files/{file_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a vault file permanently",
)
async def delete_file(
    file_id: str,
    user: User = Depends(can_upload_files),
    password: str = Depends(vault_password),
    service: VaultService = Depends(vault_service),
) -> None:
    await service.delete(user, file_id, password)


@router.post(
    "/files/{file_id}/move-out",
    response_model=FileInfo,
    summary="Move a vault file back to My Files",
)
async def move_out(
    file_id: str,
    user: User = Depends(can_upload_files),
    password: str = Depends(vault_password),
    service: VaultService = Depends(vault_service),
) -> FileInfo:
    return FileInfo.from_doc(await service.move_out(user, file_id, password))


@router.post(
    "/import/{file_id}",
    response_model=VaultFile,
    summary="Move a file from My Files into the vault (its shares are removed)",
)
async def move_in(
    file_id: str,
    user: User = Depends(can_upload_files),
    password: str = Depends(vault_password),
    service: VaultService = Depends(vault_service),
) -> VaultFile:
    return await service.move_in(user, file_id, password)
