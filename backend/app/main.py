"""FastAPI application factory and entry point."""

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging, get_logger
from app.database.session import engine


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create a configured SafeZone API instance."""
    app_settings = settings or get_settings()
    configure_logging(app_settings.log_level)
    logger = get_logger(__name__)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        logger.info(
            "application_started",
            extra={"environment": app_settings.app_env},
        )
        yield
        await engine.dispose()
        logger.info("application_stopped")

    application = FastAPI(
        title=app_settings.app_name,
        version="0.1.0",
        lifespan=lifespan,
    )

    if app_settings.allowed_frontend_origins:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=[
                str(origin).rstrip("/") for origin in app_settings.allowed_frontend_origins
            ],
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type"],
        )

    application.include_router(api_router)
    return application


app = create_app()
