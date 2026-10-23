"""Collects every route module under the /api prefix."""

from fastapi import APIRouter

from app.api.routes import (
    admin,
    admin_reports,
    analytics,
    auth,
    files,
    folders,
    health,
    shares,
    trash,
    users,
)

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(admin.router)
api_router.include_router(admin_reports.router)
api_router.include_router(files.router)
api_router.include_router(folders.router)
api_router.include_router(trash.router)
api_router.include_router(shares.router)
api_router.include_router(shares.public_router)
api_router.include_router(analytics.router)
