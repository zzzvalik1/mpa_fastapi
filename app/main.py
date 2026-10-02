"""FastAPI application entry point.

Run locally with::

    uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload

Or via the Docker setup (see ``docker-compose.yml``).
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.exception_handlers import install_exception_handlers
from app.core.logging import LOGGER_NAME, setup_logging
from app.middleware.cors import install_cors
from app.middleware.request_logging import RequestLoggingMiddleware


@asynccontextmanager
async def _lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Application lifespan — initialises logging on startup.

    Args:
        _: The FastAPI application instance (unused).

    Yields:
        ``None`` — no resources are held between startup and shutdown.
    """
    setup_logging()
    yield


def create_app() -> FastAPI:
    """Build and return the configured :class:`FastAPI` application.

    Returns:
        A ready-to-serve FastAPI instance.
    """
    app = FastAPI(
        title="MPA FastAPI",
        description="Python 3.12 / FastAPI port of the mpa_slim (Slim 4) mobile-application API.",
        version="1.0.0",
        debug=settings.app_debug,
        lifespan=_lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # Middleware (order matters: outermost first).
    install_cors(app)
    app.add_middleware(RequestLoggingMiddleware)

    # Routes
    app.include_router(api_router)

    # Health endpoint (outside /api/v1).
    @app.get("/health", tags=["meta"], summary="Liveness probe.")
    def health() -> dict[str, str]:
        """Return ``{"status": "ok"}`` if the process is alive.

        Returns:
            A small dict used by container orchestrators as a liveness probe.
        """
        return {"status": "ok"}

    # Exception handlers
    install_exception_handlers(app)

    # Make sure the logger exists even before the first request.
    setup_logging()
    app.state.logger_name = LOGGER_NAME
    return app


#: Module-level application instance used by ``uvicorn app.main:app``.
app = create_app()


__all__ = ["app", "create_app"]
