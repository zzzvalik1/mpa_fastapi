"""Эндпоинты push-воркеров."""

from __future__ import annotations

from fastapi import APIRouter, status

from app.api.v1.dependencies import PushServiceDep
from app.schemas.common import Envelope

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get(
    "/send",
    response_model=Envelope,
    status_code=status.HTTP_200_OK,
    summary="Разослать PUSH-уведомления.",
)
def send_messages(service: PushServiceDep) -> Envelope:
    """Отправить все ожидающие push-сообщения в шлюз.

    Args:
        service: Внедрённый :class:`PushService`.

    Returns:
        :class:`Envelope`, описывающий результат.
    """
    result = service.send_messages()
    return Envelope(
        success=bool(result.get("success")),
        message=result.get("message", ""),
        code=int(result.get("code", 200)),
    )


@router.get(
    "/status",
    response_model=Envelope,
    status_code=status.HTTP_200_OK,
    summary="Проверить статус PUSH-уведомлений.",
)
def status_messages(service: PushServiceDep) -> Envelope:
    """Обновить статус недавно отправленных push-сообщений."""
    result = service.status_messages()
    return Envelope(
        success=bool(result.get("success")),
        message=result.get("message", ""),
        code=int(result.get("code", 200)),
    )


@router.get(
    "/status-old",
    response_model=Envelope,
    status_code=status.HTTP_200_OK,
    summary="Проверить статус задержавшихся PUSH-уведомлений.",
)
def status_messages_old(service: PushServiceDep) -> Envelope:
    """Обновить статус давно ожидающих push-сообщений (retry 15..19)."""
    result = service.status_messages_old()
    return Envelope(
        success=bool(result.get("success")),
        message=result.get("message", ""),
        code=int(result.get("code", 200)),
    )


__all__ = ["router"]
