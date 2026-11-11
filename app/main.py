"""FastAPI application entrypoint."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.config import get_settings
from app.database import init_db
from app.deps import LoginRequiredRedirect
from app.routes.auth import router as auth_router
from app.routes.dashboard import router as dashboard_router
from app.routes.profile import router as profile_router

logger = logging.getLogger(__name__)
STATIC_DIR = Path(__file__).resolve().parent / "static"
SESSION_MAX_AGE_SECONDS = 60 * 60 * 24 * 7


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Validate configuration and initialize database tables on startup."""
    settings = get_settings()
    init_db()
    logger.info("Starting BD Job Hunter in %s mode", settings.ENV)
    yield


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()
    application = FastAPI(
        title="BD Job Hunter",
        description="Job discovery, skill matching, and application tracker for BD students.",
        version="0.1.0",
        lifespan=lifespan,
    )

    application.add_middleware(
        SessionMiddleware,
        secret_key=settings.SECRET_KEY,
        session_cookie="bd_job_hunter_session",
        same_site="lax",
        https_only=settings.ENV.lower() == "production",
        max_age=SESSION_MAX_AGE_SECONDS,
    )

    @application.exception_handler(LoginRequiredRedirect)
    async def handle_login_required(
        _request: Request,
        _exc: LoginRequiredRedirect,
    ) -> RedirectResponse:
        """Redirect unauthenticated visitors on protected pages to /login."""
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    application.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    application.include_router(auth_router)
    application.include_router(profile_router)
    application.include_router(dashboard_router)

    @application.get("/health", tags=["system"])
    def health_check() -> dict[str, str]:
        """Return service health status."""
        return {"status": "ok"}

    return application


app = create_app()
