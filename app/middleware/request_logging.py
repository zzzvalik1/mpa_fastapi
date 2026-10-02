"""Request / response logging middleware.

Logs every incoming request and the corresponding response status to the
main application logger.  This complements the per-logger rotating file
handler configured in :mod:`app.core.logging` and gives a full audit trail
of API traffic.

The middleware is intentionally lightweight — it does not read the request
body (which would interfere with streaming payloads) and only records:

* the HTTP method and path
* the originating client IP (honouring ``X-Forwarded-For``)
* the response status code
* the round-trip duration in milliseconds
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
    """Log every request and its response status."""

    def __init__(self, app: ASGIApp) -> None:
        """Initialise the middleware.

        Args:
            app: The wrapped ASGI application.
        """
        super().__init__(app)
        self.logger = get_logger()

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Process the request, log the round-trip, then return the response.

        Args:
            request: The incoming Starlette :class:`Request`.
            call_next: The next ASGI handler in the chain.

        Returns:
            The :class:`Response` produced by the downstream handler.
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
