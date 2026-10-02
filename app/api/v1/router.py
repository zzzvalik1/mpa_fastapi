"""Агрегатор всех роутеров v1 эндпоинтов.

Единый :data:`api_router`, возвращаемый этим модулем, монтируется под
``/api/v1`` модулем :mod:`app.main`.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.endpoints import (
    accounts,
    auth,
    fees,
    messages,
    push,
    resources,
    services,
    subscriber,
    tariffs,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(subscriber.router)
api_router.include_router(accounts.router)
api_router.include_router(services.router)
api_router.include_router(tariffs.router)
api_router.include_router(fees.router)
api_router.include_router(messages.router)
api_router.include_router(resources.router)
api_router.include_router(push.router)


__all__ = ["api_router"]
