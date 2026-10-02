"""Точка входа FastAPI-приложения.

Локальный запуск::

    uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload

Или через Docker-конфигурацию (см. ``docker-compose.yml``).
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
    """Жизненный цикл (lifespan) приложения — инициализирует логирование при запуске.

    Args:
        _: Экземпляр FastAPI-приложения (не используется).

    Yields:
        ``None`` — между запуском и остановкой никакие ресурсы не удерживаются.
    """
    setup_logging()
    yield


def create_app() -> FastAPI:
    """Собрать и вернуть настроенный :class:`FastAPI`-приложения.

    Returns:
        Готовый к обслуживанию экземпляр FastAPI.
    """
    app = FastAPI(
        title="MPA FastAPI",
        description="Порт на Python 3.12 / FastAPI мобильного API mpa_slim (Slim 4).",
        version="1.0.0",
        debug=settings.app_debug,
        lifespan=_lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # Middleware (порядок важен: сначала внешний).
    install_cors(app)
    app.add_middleware(RequestLoggingMiddleware)

    # Routes
    app.include_router(api_router)

    # Health-эндпоинт (вне /api/v1).
    @app.get("/health", tags=["meta"], summary="Проверка живости.")
    def health() -> dict[str, str]:
        """Вернуть ``{"status": "ok"}``, если процесс жив.

        Returns:
            Небольшой словарь, используемый оркестраторами контейнеров как проверка живости.
        """
        return {"status": "ok"}

    # Обработчики исключений
    install_exception_handlers(app)

    # Убедиться, что логгер существует ещё до первого запроса.
    setup_logging()
    app.state.logger_name = LOGGER_NAME
    return app


#: Экземпляр приложения на уровне модуля, используемый ``uvicorn app.main:app``.
app = create_app()


__all__ = ["app", "create_app"]
