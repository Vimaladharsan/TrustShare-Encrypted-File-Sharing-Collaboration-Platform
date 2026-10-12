from typing import Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile, status
from fastapi.responses import StreamingResponse
from pymongo.asynchronous.database import AsyncDatabase

from app.api.deps import can_read_files, can_upload_files
from app.db.mongo import get_mongo
from app.models import User
from app.repositories.file_repository import FileRepository
from app.schemas.file import FileInfo, FileListResponse, StorageUsageResponse
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
    allow_duplicate: bool = Query(False, description="Keep both if an identical file exists"),
    user: User = Depends(can_upload_files),
    service: FileService = Depends(file_service),
) -> FileInfo:
    doc = await service.upload(user, file, allow_duplicate)
    return FileInfo.from_doc(doc)


@router.get("", response_model=FileListResponse, summary="List my files")
async def list_files(
    q: str | None = Query(None, max_length=100, description="Search in file names"),
    category: Literal["document", "spreadsheet", "presentation", "image", "text"] | None = None,
    sort: Literal["name", "size", "date"] = "date",
    order: Literal["asc", "desc"] = "desc",
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: User = Depends(can_read_files),
    db: AsyncDatabase = Depends(get_mongo),
) -> FileListResponse:
    docs, total = await FileRepository(db).list_owned(
        str(user.id),
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


@router.get("/{file_id}/download", summary="Download the file")
async def download_file(
    file_id: str,
    user: User = Depends(can_read_files),
    service: FileService = Depends(file_service),
) -> StreamingResponse:
    doc, chunks = await service.download(user, file_id)
    name = doc["original_name"]
    ascii_name = name.encode("ascii", "replace").decode().replace('"', "'")
    return StreamingResponse(
        chunks,
        media_type=doc["mime_type"],
        headers={
            # "attachment" = always save as a file, never open/execute inside the page.
            "Content-Disposition": f'attachment; filename="{ascii_name}"; '
            f"filename*=UTF-8''{quote(name)}",
            "Content-Length": str(doc["size_bytes"]),
        },
    )
