"""Account endpoints (``/subscriber/accounts`` group)."""

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
    """Return the list of accounts owned by the subscriber.

    Args:
        uid: Authenticated user id.
        service: Injected :class:`CustomerService`.

    Returns:
        An :class:`Envelope` whose ``data`` is a list with one account dict.
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
    """Return a single account by id.

    Args:
        account_id: Path account id (must equal ``uid``).
        uid: Authenticated user id.
        service: Injected :class:`CustomerService`.

    Returns:
        An :class:`Envelope` whose ``data`` is the account dict.
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
    """Apply a ``suspend`` / ``unsuspend`` / ``promised-pay`` action.

    Args:
        account_id: Path account id.
        body: Action payload.
        uid: Authenticated user id.
        service: Injected :class:`CustomerService`.

    Returns:
        An :class:`Envelope` describing the outcome.
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
    """Return the payment URL payload.

    Args:
        account_id: Path account id.
        uid: Authenticated user id.
        service: Injected :class:`CustomerService`.
        amount: Query parameter — payment amount.

    Returns:
        An :class:`Envelope` whose ``data`` is the pay-link payload.
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
    """Return the auto-payment URL payload."""
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
    """Disable the auto-payment binding for the user.

    Returns:
        An :class:`Envelope` describing the outcome.
    """
    result = service.set_auto_pay_off(uid)
    return Envelope(
        success=bool(result.get("success")),
        data=result.get("data"),
        message=result.get("message", ""),
        code=int(result.get("code", 200)),
    )


__all__ = ["router"]
