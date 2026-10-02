"""Message endpoints (``POST /subscriber/shop``, ``POST /support/send-email``)."""

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
    """Send a shop-order email to support.

    The endpoint accepts both authenticated (JWT present) and anonymous
    requests; the helper uses the appropriate email template in each case.

    Args:
        body: Shop-request payload.
        uid: Optional authenticated user id.
        service: Injected :class:`MessageService`.

    Returns:
        An :class:`Envelope` whose ``data`` contains the email body preview.
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
    """Send a support email.

    Args:
        body: Support-email payload.
        service: Injected :class:`MessageService`.

    Returns:
        An :class:`Envelope` describing the outcome.
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
