from fastapi import APIRouter, Depends, Query, Request, status
from pymongo.asynchronous.database import AsyncDatabase

from app.api.deps import can_delete_files, can_manage_folders, can_read_files
from app.db.mongo import get_mongo
from app.models import User
from app.schemas.folder import (
    FolderCreate,
    FolderDetail,
    FolderInfo,
    FolderListResponse,
    FolderUpdate,
)
from app.services.folder_service import FolderService
from app.storage.local import LocalStorage, get_storage

router = APIRouter(prefix="/folders", tags=["folders"])


def folder_service(
    request: Request,
    db: AsyncDatabase = Depends(get_mongo),
    storage: LocalStorage = Depends(get_storage),
) -> FolderService:
    return FolderService(db, request, storage)


@router.get("", response_model=FolderListResponse, summary="List folders")
async def list_folders(
    parent_id: str | None = Query(None, description="Parent folder (empty = top level)"),
    trashed: bool = Query(False, description="List folders in the trash instead"),
    user: User = Depends(can_read_files),
    service: FolderService = Depends(folder_service),
) -> FolderListResponse:
    docs = (
        await service.list_trashed(user)
        if trashed
        else await service.list_children(user, parent_id)
    )
    return FolderListResponse(items=[FolderInfo.from_doc(d) for d in docs])


@router.post(
    "", response_model=FolderInfo, status_code=status.HTTP_201_CREATED, summary="Create a folder"
)
async def create_folder(
    data: FolderCreate,
    user: User = Depends(can_manage_folders),
    service: FolderService = Depends(folder_service),
) -> FolderInfo:
    return FolderInfo.from_doc(await service.create(user, data.name, data.parent_id))


@router.get("/{folder_id}", response_model=FolderDetail, summary="Folder details + breadcrumbs")
async def get_folder(
    folder_id: str,
    user: User = Depends(can_read_files),
    service: FolderService = Depends(folder_service),
) -> FolderDetail:
    doc = await service.owned(user, folder_id)
    info = FolderInfo.from_doc(doc)
    return FolderDetail(**info.model_dump(), breadcrumbs=await service.breadcrumbs(doc))


@router.patch("/{folder_id}", response_model=FolderInfo, summary="Rename and/or move a folder")
async def update_folder(
    folder_id: str,
    data: FolderUpdate,
    user: User = Depends(can_manage_folders),
    service: FolderService = Depends(folder_service),
) -> FolderInfo:
    # model_fields_set tells "parent_id": null (move to top level) apart from "not sent".
    changes = data.model_dump(include=data.model_fields_set)
    return FolderInfo.from_doc(await service.update(user, folder_id, changes))


@router.post(
    "/{folder_id}/trash",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Move the folder and everything inside it to the trash",
)
async def trash_folder(
    folder_id: str,
    user: User = Depends(can_manage_folders),
    service: FolderService = Depends(folder_service),
) -> None:
    await service.trash(user, folder_id)


@router.post("/{folder_id}/restore", response_model=FolderInfo, summary="Restore from trash")
async def restore_folder(
    folder_id: str,
    user: User = Depends(can_manage_folders),
    service: FolderService = Depends(folder_service),
) -> FolderInfo:
    return FolderInfo.from_doc(await service.restore(user, folder_id))


@router.delete(
    "/{folder_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a trashed folder and everything inside it forever (cannot be undone)",
    dependencies=[Depends(can_delete_files)],
)
async def delete_folder(
    folder_id: str,
    user: User = Depends(can_manage_folders),
    service: FolderService = Depends(folder_service),
) -> None:
    await service.delete_forever(user, folder_id)
