"""Эндпоинты аккаунтов (группа ``/subscriber/accounts``)."""

from __future__ import annotations

from fastapi import APIRouter, Query, status

from app.api.v1.dependencies import CurrentUid, CustomerServiceDep
from app.schemas.common import Envelope
from app.schemas.customer import ChangeAccountRequest

router = APIRouter(prefix="/subscriber/accounts", tags=["accounts"])


@router.get(
    "",
    response_model=Envelope[list],
    status_code=status.HTTP_200_OK,
    summary="Получить информацию об аккаунтах абонента.",
)
def get_accounts(
    uid: CurrentUid,
    service: CustomerServiceDep,
) -> Envelope[list]:
    """Вернуть список аккаунтов подписчика.

    Args:
        uid: id аутентифицированного пользователя.
        service: Внедрённый :class:`CustomerService`.

    Returns:
        :class:`Envelope`, у которого ``data`` — список с одним dict аккаунта.
    """
    return Envelope(success=True, data=service.get_accounts(uid), message="success", code=200)


@router.get(
    "/{account_id}",
    response_model=Envelope[dict],
    status_code=status.HTTP_200_OK,
    summary="Получить информацию о конкретном лицевом счёте.",
)
def get_account(
    account_id: int,
    uid: CurrentUid,
    service: CustomerServiceDep,
) -> Envelope[dict]:
    """Вернуть один аккаунт по id.

    Args:
        account_id: id аккаунта из пути (должен совпадать с ``uid``).
        uid: id аутентифицированного пользователя.
        service: Внедрённый :class:`CustomerService`.

    Returns:
        :class:`Envelope`, у которого ``data`` — dict аккаунта.
    """
    return Envelope(success=True, data=service.get_account(uid, account_id), message="success", code=200)


@router.patch(
    "/{account_id}",
    response_model=Envelope[None],
    status_code=status.HTTP_200_OK,
    summary="Заблокировать/разблокировать аккаунт; установить обещанный платёж.",
)
def change_account(
    account_id: int,
    body: ChangeAccountRequest,
    uid: CurrentUid,
    service: CustomerServiceDep,
) -> Envelope[None]:
    """Применить действие ``suspend`` / ``unsuspend`` / ``promised-pay``.

    Args:
        account_id: id аккаунта из пути.
        body: Полезная нагрузка действия.
        uid: id аутентифицированного пользователя.
        service: Внедрённый :class:`CustomerService`.

    Returns:
        :class:`Envelope`, описывающий результат.
    """
    result = service.change_account(
        uid, account_id, body.action, body.date_start, body.date_end
    )
    return Envelope(
        success=bool(result.get("success")),
        message=result.get("message", ""),
        code=int(result.get("code", 200)),
    )


@router.get(
    "/{account_id}/pay-link",
    response_model=Envelope[dict],
    status_code=status.HTTP_200_OK,
    summary="Получить ссылку для платежа.",
)
def get_pay_link(
    account_id: int,
    uid: CurrentUid,
    service: CustomerServiceDep,
    amount: float = Query(..., ge=0, description="Сумма платежа."),
) -> Envelope[dict]:
    """Вернуть полезную нагрузку с URL для платежа.

    Args:
        account_id: id аккаунта из пути.
        uid: id аутентифицированного пользователя.
        service: Внедрённый :class:`CustomerService`.
        amount: Query-параметр — сумма платежа.

    Returns:
        :class:`Envelope`, у которого ``data`` — полезная нагрузка pay-link.
    """
    return Envelope(success=True, data=service.get_pay_link(uid, amount), message="success", code=200)


@router.get(
    "/{account_id}/auto-payment-link",
    response_model=Envelope[dict],
    status_code=status.HTTP_200_OK,
    summary="Получить ссылку для автоплатежа.",
)
def get_auto_pay_link(
    account_id: int,
    uid: CurrentUid,
    service: CustomerServiceDep,
    amount: float = Query(..., ge=0, description="Сумма автоплатежа."),
) -> Envelope[dict]:
    """Вернуть полезную нагрузку с URL для автоплатежа."""
    return Envelope(success=True, data=service.get_auto_pay_link(uid, amount), message="success", code=200)


@router.get(
    "/{account_id}/auto-payment-off",
    response_model=Envelope,
    status_code=status.HTTP_200_OK,
    summary="Отключить автоплатёж.",
)
def set_auto_pay_off(
    account_id: int,
    uid: CurrentUid,
    service: CustomerServiceDep,
) -> Envelope:
    """Отключить привязку автоплатежа для пользователя.

    Returns:
        :class:`Envelope`, описывающий результат.
    """
    result = service.set_auto_pay_off(uid)
    return Envelope(
        success=bool(result.get("success")),
        data=result.get("data"),
        message=result.get("message", ""),
        code=int(result.get("code", 200)),
    )


__all__ = ["router"]
