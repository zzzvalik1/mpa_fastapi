"""CORS middleware factory."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


def install_cors(app: FastAPI) -> None:
    """Register permissive CORS middleware on the given app.

    Mirrors the original PHP ``App/Cors.php`` configuration:

    * ``Access-Control-Allow-Origin: *``
    * allowed headers: ``X-Requested-With, Content-Type, Accept, Origin, Authorization``
    * allowed methods: ``GET, POST, PUT, DELETE, PATCH, OPTIONS``

    Args:
        app: The FastAPI application instance.
    """
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        allow_headers=[
            "X-Requested-With",
            "Content-Type",
            "Accept",
            "Origin",
            "Authorization",
        ],
    )


__all__ = ["install_cors"]
