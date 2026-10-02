"""Central exception handlers.

These handlers convert the application-defined exceptions (see
:mod:`app.core.exceptions`) and a few FastAPI / Pydantic errors into the
canonical JSON envelope used by the mobile application:

::

    {
        "success": false,
        "message": "<error message>",
        "code": <http status>
    }
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import AppError, DatabaseError
from app.core.logging import get_logger


def _envelope(success: bool, message: str, code: int, **extra: Any) -> dict[str, Any]:
    """Build the canonical response envelope.

    Args:
        success: ``True`` for success responses, ``False`` for errors.
        message: Human-readable message.
        code: HTTP status code.
        **extra: Additional keys to merge into the envelope (e.g. ``data``).

    Returns:
        A dict suitable for :class:`fastapi.responses.JSONResponse`.
    """
    payload: dict[str, Any] = {
        "success": success,
        "message": message,
        "code": code,
    }
    payload.update(extra)
    return payload


def install_exception_handlers(app: FastAPI) -> None:
    """Register all exception handlers on the given FastAPI application.

    Args:
        app: The FastAPI application instance.
    """
    logger = get_logger()

    # ------------------------------------------------------------------ #
    # AppError — every business / domain error inherits from it.
    # ------------------------------------------------------------------ #
    @app.exception_handler(AppError)
    async def _handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        """Convert an :class:`AppError` to the canonical JSON envelope."""
        logger.warning("AppError: %s (status=%s)", exc.message, exc.status_code)
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(False, exc.message, exc.status_code),
            media_type="application/problem+json",
        )

    # ------------------------------------------------------------------ #
    # DatabaseError — log full traceback, return 502.
    # ------------------------------------------------------------------ #
    @app.exception_handler(DatabaseError)
    async def _handle_database_error(_: Request, exc: DatabaseError) -> JSONResponse:
        """Convert a :class:`DatabaseError` to a 502 response."""
        logger.exception("Database error: %s", exc.message)
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(False, exc.message, exc.status_code),
            media_type="application/problem+json",
        )

    # ------------------------------------------------------------------ #
    # FastAPI request validation errors (Pydantic v2).
    # ------------------------------------------------------------------ #
    @app.exception_handler(RequestValidationError)
    async def _handle_request_validation_error(
        _: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Return a 422 with the canonical envelope plus a ``details`` list."""
        logger.warning("Validation error: %s", exc.errors())
        return JSONResponse(
            status_code=422,
            content=_envelope(
                False,
                "validation error",
                422,
                details=exc.errors(),
            ),
            media_type="application/problem+json",
        )

    # ------------------------------------------------------------------ #
    # Starlette HTTPException (404, 405, ...) — keep FastAPI's behaviour.
    # ------------------------------------------------------------------ #
    @app.exception_handler(StarletteHTTPException)
    async def _handle_http_exception(
        _: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        """Convert a Starlette :class:`HTTPException` to the JSON envelope."""
        message = exc.detail if isinstance(exc.detail, str) else "http error"
        logger.info("HTTP %s — %s", exc.status_code, message)
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(False, message, exc.status_code),
            media_type="application/problem+json",
        )

    # ------------------------------------------------------------------ #
    # Catch-all for any other unhandled exception.
    # ------------------------------------------------------------------ #
    @app.exception_handler(Exception)
    async def _handle_unexpected_error(_: Request, exc: Exception) -> JSONResponse:
        """Convert any unexpected exception to a 500 response.

        The original exception is logged with full traceback.  The error
        message returned to the client is generic on purpose, to avoid
        leaking internal details.
        """
        logger.exception("Unhandled exception: %s", exc)
        return JSONResponse(
            status_code=500,
            content=_envelope(False, "internal server error", 500),
            media_type="application/problem+json",
        )


__all__ = ["install_exception_handlers", "_envelope"]
