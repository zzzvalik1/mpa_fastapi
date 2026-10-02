"""Логирование запросов / ответов (middleware).

Логирует каждый входящий запрос и соответствующий статус ответа в основной
логгер приложения. Это дополняет настроенный в :mod:`app.core.logging`
ротируемый по времени файловый обработчик на каждый логгер и даёт полный
аудиторский след API-трафика.

Middleware намеренно лёгкий — он не читает тело запроса (что мешало бы
стриминговым полезным нагрузкам) и фиксирует только:

* HTTP-метод и путь
* исходящий IP клиента (с учётом ``X-Forwarded-For``)
* статус-код ответа
* длительность кругового пути в миллисекундах
"""

from __future__ import annotations

import time
import uuid
from typing import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from app.core.logging import get_logger


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Логировать каждый запрос и статус его ответа."""

    def __init__(self, app: ASGIApp) -> None:
        """Инициализировать middleware.

        Args:
            app: Обёрнутое ASGI-приложение.
        """
        super().__init__(app)
        self.logger = get_logger()

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Обработать запрос, залогировать круговой путь, затем вернуть ответ.

        Args:
            request: Входящий Starlette :class:`Request`.
            call_next: Следующий ASGI-обработчик в цепочке.

        Returns:
            :class:`Response`, полученный от нижестоящего обработчика.
        """
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        forwarded = request.headers.get("x-forwarded-for")
        client_ip = (
            forwarded.split(",")[0].strip()
            if forwarded
            else (request.client.host if request.client else "-")
        )

        start = time.perf_counter()
        response: Response | None = None
        try:
            response = await call_next(request)
            return response
        finally:
            duration_ms = (time.perf_counter() - start) * 1000.0
            status_code = response.status_code if response is not None else 500
            self.logger.info(
                "req_id=%s %s %s -> %s (%.1f ms) ip=%s",
                request_id,
                request.method,
                request.url.path,
                status_code,
                duration_ms,
                client_ip,
            )


__all__ = ["RequestLoggingMiddleware"]
