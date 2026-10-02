"""Эндпоинты сообщений (``POST /subscriber/shop``, ``POST /support/send-email``)."""

from __future__ import annotations

from fastapi import APIRouter, status

from app.api.v1.dependencies import MessageServiceDep, OptionalUid
from app.schemas.common import Envelope
from app.schemas.message import ShopRequest, SupportEmailRequest

router = APIRouter(tags=["messages"])


@router.post(
    "/subscriber/shop",
    response_model=Envelope,
    status_code=status.HTTP_200_OK,
    summary="Отправка заявки на почту (shop request).",
)
def message_auth(
    body: ShopRequest,
    uid: OptionalUid,
    service: MessageServiceDep,
) -> Envelope:
    """Отправить заявку из магазина в поддержку.

    Эндпоинт принимает как аутентифицированные (с JWT), так и анонимные
    запросы; хелпер использует соответствующий email-шаблон в каждом случае.

    Args:
        body: Полезная нагрузка shop-запроса.
        uid: Необязательный id аутентифицированного пользователя.
        service: Внедрённый :class:`MessageService`.

    Returns:
        :class:`Envelope`, у которого ``data`` содержит предпросмотр тела письма.
    """
    result = service.message_auth(
        uid,
        good_id=body.goodId,
        address=body.address,
        phone_number=body.phone_number,
        email=body.email,
        comment=body.comment,
    )
    return Envelope(
        success=True,
        data=result.get("data"),
        message="success",
        code=200,
    )


@router.post(
    "/support/send-email",
    response_model=Envelope,
    status_code=status.HTTP_200_OK,
    summary="Отправить сообщение в тех. поддержку.",
)
def send_support_email(
    body: SupportEmailRequest,
    service: MessageServiceDep,
) -> Envelope:
    """Отправить письмо в тех. поддержку.

    Args:
        body: Полезная нагрузка support-email.
        service: Внедрённый :class:`MessageService`.

    Returns:
        :class:`Envelope`, описывающий результат.
    """
    result = service.send_support_email(
        account=body.account,
        phone_number=body.phone_number,
        email=body.email,
        message=body.message,
    )
    return Envelope(
        success=bool(result.get("success")),
        message=result.get("message", ""),
        code=int(result.get("code", 200)),
    )


__all__ = ["router"]
