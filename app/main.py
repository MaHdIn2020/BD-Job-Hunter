"""FastAPI application entrypoint."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import get_settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Validate configuration on startup."""
    settings = get_settings()
    logger.info("Starting BD Job Hunter in %s mode", settings.ENV)
    yield


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    get_settings()
    application = FastAPI(
        title="BD Job Hunter",
        description="Job discovery, skill matching, and application tracker for BD students.",
        version="0.1.0",
        lifespan=lifespan,
    )

    @application.get("/health", tags=["system"])
    def health_check() -> dict[str, str]:
        """Return service health status."""
        return {"status": "ok"}

    return application


app = create_app()
