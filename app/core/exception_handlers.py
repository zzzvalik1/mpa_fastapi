"""Центральные обработчики исключений.

Эти обработчики преобразуют определённые в приложении исключения (см.
:mod:`app.core.exceptions`) и ряд ошибок FastAPI / Pydantic в канонический
JSON-конверт, используемый мобильным приложением:

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
    """Построить канонический конверт ответа.

    Args:
        success: ``True`` для успешных ответов, ``False`` для ошибок.
        message: Человекочитаемое сообщение.
        code: HTTP-код статуса.
        **extra: Дополнительные ключи для слияния в конверт (например ``data``).

    Returns:
        Словарь, подходящий для :class:`fastapi.responses.JSONResponse`.
    """
    payload: dict[str, Any] = {
        "success": success,
        "message": message,
        "code": code,
    }
    payload.update(extra)
    return payload


def install_exception_handlers(app: FastAPI) -> None:
    """Зарегистрировать все обработчики исключений в данном FastAPI-приложении.

    Args:
        app: Экземпляр FastAPI-приложения.
    """
    logger = get_logger()

    # ------------------------------------------------------------------ #
    # AppError — от него наследуется каждая бизнес / доменная ошибка.
    # ------------------------------------------------------------------ #
    @app.exception_handler(AppError)
    async def _handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        """Преобразовать :class:`AppError` в канонический JSON-конверт."""
        logger.warning("AppError: %s (status=%s)", exc.message, exc.status_code)
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(False, exc.message, exc.status_code),
            media_type="application/problem+json",
        )

    # ------------------------------------------------------------------ #
    # DatabaseError — записать полный traceback, вернуть 502.
    # ------------------------------------------------------------------ #
    @app.exception_handler(DatabaseError)
    async def _handle_database_error(_: Request, exc: DatabaseError) -> JSONResponse:
        """Преобразовать :class:`DatabaseError` в ответ 502."""
        logger.exception("Database error: %s", exc.message)
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(False, exc.message, exc.status_code),
            media_type="application/problem+json",
        )

    # ------------------------------------------------------------------ #
    # Ошибки валидации запросов FastAPI (Pydantic v2).
    # ------------------------------------------------------------------ #
    @app.exception_handler(RequestValidationError)
    async def _handle_request_validation_error(
        _: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Вернуть 422 с каноническим конвертом плюс список ``details``."""
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
    # Starlette HTTPException (404, 405, ...) — сохранить поведение FastAPI.
    # ------------------------------------------------------------------ #
    @app.exception_handler(StarletteHTTPException)
    async def _handle_http_exception(
        _: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        """Преобразовать Starlette :class:`HTTPException` в JSON-конверт."""
        message = exc.detail if isinstance(exc.detail, str) else "http error"
        logger.info("HTTP %s — %s", exc.status_code, message)
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(False, message, exc.status_code),
            media_type="application/problem+json",
        )

    # ------------------------------------------------------------------ #
    # Перехватчик для любого иного необработанного исключения.
    # ------------------------------------------------------------------ #
    @app.exception_handler(Exception)
    async def _handle_unexpected_error(_: Request, exc: Exception) -> JSONResponse:
        """Преобразовать любое непредвиденное исключение в ответ 500.

        Исходное исключение записывается в лог с полным traceback. Сообщение
        об ошибке, возвращаемое клиенту, намеренно общее, чтобы избежать
        утечки внутренних деталей.
        """
        logger.exception("Unhandled exception: %s", exc)
        return JSONResponse(
            status_code=500,
            content=_envelope(False, "internal server error", 500),
            media_type="application/problem+json",
        )


__all__ = ["install_exception_handlers", "_envelope"]
