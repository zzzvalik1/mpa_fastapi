"""Эндпоинты подписчика (``GET /subscriber``, ``GET /resources/promised-pay-terms``)."""

from __future__ import annotations

from fastapi import APIRouter, status

from app.api.v1.dependencies import CurrentUid, CustomerServiceDep
from app.schemas.common import Envelope

router = APIRouter(prefix="/subscriber", tags=["subscriber"])


@router.get(
    "",
    response_model=Envelope[dict],
    status_code=status.HTTP_200_OK,
    summary="Получить информацию об абоненте.",
)
def get_subscriber(
    uid: CurrentUid,
    service: CustomerServiceDep,
) -> Envelope[dict]:
    """Вернуть профиль абонента + сводку активного аккаунта.

    Args:
        uid: id аутентифицированного пользователя.
        service: Внедрённый :class:`CustomerService`.

    Returns:
        :class:`Envelope`, у которого ``data`` — полезная нагрузка абонента.
    """
    return Envelope(success=True, data=service.get_subscriber(uid), message="success", code=200)


__all__ = ["router"]
