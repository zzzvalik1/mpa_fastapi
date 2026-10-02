"""Эндпоинты ресурсов (``GET /resources/promised-pay-terms``)."""

from __future__ import annotations

from fastapi import APIRouter, status

from app.api.v1.dependencies import CurrentUid, CustomerServiceDep
from app.schemas.common import Envelope

router = APIRouter(prefix="/resources", tags=["resources"])


@router.get(
    "/promised-pay-terms",
    response_model=Envelope[str],
    status_code=status.HTTP_200_OK,
    summary="Получить информацию об обещанном платеже.",
)
def promised_pay_terms(
    uid: CurrentUid,
    service: CustomerServiceDep,
) -> Envelope[str]:
    """Вернуть статический HTML с описанием условий обещанного платежа.

    Args:
        uid: id аутентифицированного пользователя.
        service: Внедрённый :class:`CustomerService`.

    Returns:
        :class:`Envelope`, у которого ``data`` — HTML-строка.
    """
    return Envelope(
        success=True,
        data=service.promised_pay_terms(uid),
        message="success",
        code=200,
    )


__all__ = ["router"]
