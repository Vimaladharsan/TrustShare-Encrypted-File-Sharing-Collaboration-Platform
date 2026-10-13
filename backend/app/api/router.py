"""Collects every route module under the /api prefix."""

from fastapi import APIRouter

from app.api.routes import admin, auth, files, folders, health, trash, users

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(admin.router)
api_router.include_router(files.router)
api_router.include_router(folders.router)
api_router.include_router(trash.router)
