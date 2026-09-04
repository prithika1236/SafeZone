"""Top-level API router registration."""

from fastapi import APIRouter

from app.api.auth import router as auth_router
from app.api.crimes import router as crimes_router
from app.api.prp import router as prp_router
from app.api.routes.health import router as health_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(crimes_router)
api_router.include_router(prp_router)
