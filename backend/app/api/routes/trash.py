from fastapi import APIRouter, Depends, Request
from pymongo.asynchronous.database import AsyncDatabase

from app.api.deps import can_delete_files, can_update_files
from app.db.mongo import get_mongo
from app.models import User
from app.schemas.trash import BulkResult, TrashSelection
from app.services.trash_service import TrashService
from app.storage.secure_store import SecureFileStore, get_file_store

router = APIRouter(prefix="/trash", tags=["trash"])


def trash_service(
    request: Request,
    db: AsyncDatabase = Depends(get_mongo),
    storage: SecureFileStore = Depends(get_file_store),
) -> TrashService:
    return TrashService(db, storage, request)


@router.post("/restore", response_model=BulkResult, summary="Restore the selected items")
async def restore_selected(
    data: TrashSelection,
    user: User = Depends(can_update_files),
    service: TrashService = Depends(trash_service),
) -> BulkResult:
    return BulkResult(**await service.restore(user, data.file_ids, data.folder_ids))


@router.post(
    "/delete",
    response_model=BulkResult,
    summary="Permanently delete the selected items (cannot be undone)",
)
async def delete_selected(
    data: TrashSelection,
    user: User = Depends(can_delete_files),
    service: TrashService = Depends(trash_service),
) -> BulkResult:
    return BulkResult(**await service.delete(user, data.file_ids, data.folder_ids))


@router.post("/restore-all", response_model=BulkResult, summary="Restore everything in the trash")
async def restore_all(
    user: User = Depends(can_update_files),
    service: TrashService = Depends(trash_service),
) -> BulkResult:
    return BulkResult(**await service.restore_all(user))


@router.post(
    "/empty",
    response_model=BulkResult,
    summary="Permanently delete everything in the trash (cannot be undone)",
)
async def empty_trash(
    user: User = Depends(can_delete_files),
    service: TrashService = Depends(trash_service),
) -> BulkResult:
    return BulkResult(**await service.empty(user))
