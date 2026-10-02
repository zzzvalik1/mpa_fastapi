"""Эндпоинты платежей (``POST .../transactions``)."""

from __future__ import annotations

from fastapi import APIRouter, status

from app.api.v1.dependencies import CurrentUid, FeeServiceDep
from app.schemas.common import Envelope
from app.schemas.fee import TransactionsRequest

router = APIRouter(tags=["fees"])


@router.post(
    "/subscriber/accounts/{account_id}/transactions",
    response_model=Envelope[list],
    status_code=status.HTTP_200_OK,
    summary="Получить транзакции по лицевому счёту.",
)
def get_transactions(
    account_id: int,
    body: TransactionsRequest,
    uid: CurrentUid,
    service: FeeServiceDep,
) -> Envelope[list]:
    """Вернуть историю транзакций для указанного аккаунта.

    Args:
        account_id: id аккаунта из пути.
        body: Необязательный фильтр диапазона дат.
        uid: id аутентифицированного пользователя.
        service: Внедрённый :class:`FeeService`.

    Returns:
        :class:`Envelope`, у которого ``data`` — список транзакций.
    """
    transactions = service.get_transactions(
        uid, account_id, body.start_date, body.end_date
    )
    return Envelope(success=True, data=transactions, message="success", code=200)


__all__ = ["router"]
