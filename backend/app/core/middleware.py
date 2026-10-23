import logging
import re
import time
import uuid

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import RequestResponseEndpoint

from app.core.config import get_settings
from app.core.errors import error_body
from app.core.logging import request_id_ctx

logger = logging.getLogger("app.request")

SHARE_TOKEN = re.compile(r"^(/api/s/)[^/]+")

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",  # browser must not guess file types
    "X-Frame-Options": "DENY",  # page can't be embedded in an iframe (clickjacking)
    "Referrer-Policy": "strict-origin-when-cross-origin",
}


def register_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def request_context(request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Runs around every request: assigns an ID, adds security headers, logs timing."""
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
        token = request_id_ctx.set(request_id)
        start = time.perf_counter()
        try:
            response = _reject_oversized_upload(request) or await call_next(request)
            response.headers["X-Request-ID"] = request_id
            for name, value in SECURITY_HEADERS.items():
                response.headers.setdefault(name, value)
            elapsed_ms = (time.perf_counter() - start) * 1000
            logger.info(
                "%s %s -> %s (%.1f ms)",
                request.method,
                safe_path(request.url.path),
                response.status_code,
                elapsed_ms,
            )
            return response
        finally:
            request_id_ctx.reset(token)


def safe_path(path: str) -> str:
    """The request path for logs, with share-link tokens hidden (a token is a password)."""
    return SHARE_TOKEN.sub(r"\g<1>***", path)


def _reject_oversized_upload(request: Request) -> Response | None:
    """Refuse an upload whose declared size is already too big, before reading the body.
    (Uploads without a size header are still stopped while streaming, in FileService.)"""
    if request.method != "POST" or request.url.path != "/api/files":
        return None
    settings = get_settings()
    declared = request.headers.get("content-length", "")
    # Allow 1 MB extra for the multipart form wrapping around the file.
    if declared.isdigit() and int(declared) > settings.max_upload_bytes + 1024 * 1024:
        return JSONResponse(
            status_code=413,
            content=error_body(
                "FILE_TOO_LARGE", f"File exceeds the {settings.max_upload_mb} MB limit."
            ),
        )
    return None
