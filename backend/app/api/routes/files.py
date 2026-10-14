from typing import Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile, status
from fastapi.responses import StreamingResponse
from pymongo.asynchronous.database import AsyncDatabase

from app.api.deps import can_delete_files, can_read_files, can_update_files, can_upload_files
from app.core.errors import AppError
from app.db.mongo import get_mongo
from app.models import User
from app.repositories.file_repository import ALL_FOLDERS, FileRepository
from app.repositories.folder_repository import FolderRepository
from app.schemas.file import FileInfo, FileListResponse, FileUpdate, StorageUsageResponse
from app.services.file_service import FileService
from app.storage.local import LocalStorage, get_storage

router = APIRouter(prefix="/files", tags=["files"])


def file_service(
    request: Request,
    db: AsyncDatabase = Depends(get_mongo),
    storage: LocalStorage = Depends(get_storage),
) -> FileService:
    return FileService(db, storage, request)


@router.post(
    "",
    response_model=FileInfo,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a file (PDF, DOCX, XLSX, PPTX, TXT, CSV, PNG, JPG; max 25 MB)",
)
async def upload_file(
    file: UploadFile = File(..., description="The file to upload"),
    folder_id: str | None = Query(None, description="Folder to upload into (empty = top level)"),
    allow_duplicate: bool = Query(False, description="Keep both if an identical file exists"),
    user: User = Depends(can_upload_files),
    service: FileService = Depends(file_service),
) -> FileInfo:
    doc = await service.upload(user, file, folder_id, allow_duplicate)
    return FileInfo.from_doc(doc)


@router.get("", response_model=FileListResponse, summary="List my files")
async def list_files(
    folder_id: str | None = Query(
        None, description='Folder to list (empty = top level, "all" = every folder)'
    ),
    trashed: bool = Query(False, description="List the trash instead"),
    q: str | None = Query(None, max_length=100, description="Search in file names"),
    category: Literal["document", "spreadsheet", "presentation", "image", "text"] | None = None,
    sort: Literal["name", "size", "date"] = "date",
    order: Literal["asc", "desc"] = "desc",
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: User = Depends(can_read_files),
    db: AsyncDatabase = Depends(get_mongo),
) -> FileListResponse:
    folder = None
    if folder_id == ALL_FOLDERS:
        folder = ALL_FOLDERS
    elif folder_id:
        found = await FolderRepository(db).get_active_owned(str(user.id), folder_id)
        if found is None:
            raise AppError("FOLDER_NOT_FOUND", "Folder not found.", 404)
        folder = found["_id"]

    docs, total = await FileRepository(db).list_owned(
        str(user.id),
        folder=folder,
        trashed=trashed,
        search=q,
        category=category,
        sort=sort,
        order=order,
        limit=limit,
        offset=offset,
    )
    return FileListResponse(items=[FileInfo.from_doc(d) for d in docs], total=total)


@router.get("/usage", response_model=StorageUsageResponse, summary="My storage used vs quota")
async def storage_usage(
    user: User = Depends(can_read_files),
    db: AsyncDatabase = Depends(get_mongo),
) -> StorageUsageResponse:
    used = await FileRepository(db).used_bytes(str(user.id))
    return StorageUsageResponse(used_bytes=used, quota_bytes=user.storage_quota_bytes)


@router.get("/{file_id}", response_model=FileInfo, summary="File details")
async def get_file(
    file_id: str,
    user: User = Depends(can_read_files),
    service: FileService = Depends(file_service),
) -> FileInfo:
    return FileInfo.from_doc(await service.get_for_read(user, file_id))


def _disposition(kind: str, name: str) -> str:
    ascii_name = name.encode("ascii", "replace").decode().replace('"', "'")
    return f"{kind}; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(name)}"


@router.get("/{file_id}/download", summary="Download the file")
async def download_file(
    file_id: str,
    user: User = Depends(can_read_files),
    service: FileService = Depends(file_service),
) -> StreamingResponse:
    doc, chunks = await service.download(user, file_id)
    return StreamingResponse(
        chunks,
        media_type=doc["mime_type"],
        headers={
            # "attachment" = always save as a file, never open/execute inside the page.
            "Content-Disposition": _disposition("attachment", doc["original_name"]),
            "Content-Length": str(doc["size_bytes"]),
        },
    )


@router.get(
    "/{file_id}/preview",
    summary="Show the file in the browser (PDF, images, TXT, CSV only)",
)
async def preview_file(
    file_id: str,
    user: User = Depends(can_read_files),
    service: FileService = Depends(file_service),
) -> StreamingResponse:
    doc, chunks = await service.preview(user, file_id)
    # Text is always sent as plain text, so it can never be interpreted as HTML.
    is_text = doc["extension"] in {"txt", "csv"}
    media_type = "text/plain; charset=utf-8" if is_text else doc["mime_type"]
    return StreamingResponse(
        chunks,
        media_type=media_type,
        headers={
            "Content-Disposition": _disposition("inline", doc["original_name"]),
            "Content-Length": str(doc["size_bytes"]),
            # If the file is ever opened directly, it runs in a sandbox: no scripts, no forms,
            # no access to our site's cookies or pages.
            "Content-Security-Policy": "sandbox; default-src 'none'; img-src 'self'",
            "Cache-Control": "private, no-store",
        },
    )


@router.patch("/{file_id}", response_model=FileInfo, summary="Rename and/or move a file")
async def update_file(
    file_id: str,
    data: FileUpdate,
    user: User = Depends(can_update_files),
    service: FileService = Depends(file_service),
) -> FileInfo:
    # model_fields_set tells "folder_id": null (move to top level) apart from "not sent".
    changes = data.model_dump(include=data.model_fields_set)
    return FileInfo.from_doc(await service.update(user, file_id, changes))


@router.post("/{file_id}/trash", status_code=status.HTTP_204_NO_CONTENT, summary="Move to trash")
async def trash_file(
    file_id: str,
    user: User = Depends(can_update_files),
    service: FileService = Depends(file_service),
) -> None:
    await service.trash(user, file_id)


@router.post("/{file_id}/restore", response_model=FileInfo, summary="Restore from trash")
async def restore_file(
    file_id: str,
    user: User = Depends(can_update_files),
    service: FileService = Depends(file_service),
) -> FileInfo:
    return FileInfo.from_doc(await service.restore(user, file_id))


@router.delete(
    "/{file_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete forever (cannot be undone)",
)
async def delete_file(
    file_id: str,
    user: User = Depends(can_delete_files),
    service: FileService = Depends(file_service),
) -> None:
    await service.delete_forever(user, file_id)
