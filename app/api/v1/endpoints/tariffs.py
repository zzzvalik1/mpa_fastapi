"""Tariff endpoints (``GET .../tariffs``)."""

from __future__ import annotations

from fastapi import APIRouter, status

from app.api.v1.dependencies import CurrentUid, TariffServiceDep
from app.schemas.common import Envelope

router = APIRouter(tags=["tariffs"])


@router.get(
    "/subscriber/accounts/{account_id}/services/{service_id}/tariffs",
    response_model=Envelope[list],
    status_code=status.HTTP_200_OK,
    summary="Получить доступные тарифы для смены.",
)
def get_tariffs(
    account_id: int,
    service_id: int,
    uid: CurrentUid,
    service: TariffServiceDep,
) -> Envelope[list]:
    """Return the list of tariffs available for switching.

    Args:
        account_id: Path account id.
        service_id: Path service id.
        uid: Authenticated user id.
        service: Injected :class:`TariffService`.

    Returns:
        An :class:`Envelope` whose ``data`` is the tariff list.
    """
    return Envelope(
        success=True,
        data=service.get_tariffs(uid, account_id, service_id),
        message="success",
        code=200,
    )


__all__ = ["router"]
