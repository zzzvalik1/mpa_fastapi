"""Push-notification worker endpoints."""

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
    """Flush all waiting push messages to the gateway.

    Args:
        service: Injected :class:`PushService`.

    Returns:
        An :class:`Envelope` describing the outcome.
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
    """Refresh the status of recently-sent push messages."""
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
    """Refresh the status of long-pending push messages (retry 15..19)."""
    result = service.status_messages_old()
    return Envelope(
        success=bool(result.get("success")),
        message=result.get("message", ""),
        code=int(result.get("code", 200)),
    )


__all__ = ["router"]
