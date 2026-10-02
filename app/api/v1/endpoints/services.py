"""Service endpoints (``/subscriber/accounts/{account_id}/services`` group)."""

from __future__ import annotations

from fastapi import APIRouter, status

from app.api.v1.dependencies import CurrentUid, ServiceServiceDep
from app.schemas.common import Envelope
from app.schemas.service import ChangeAddServiceRequest, ChangeServiceRequest

router = APIRouter(tags=["services"])


@router.get(
    "/subscriber/accounts/{account_id}/services",
    response_model=Envelope[list],
    status_code=status.HTTP_200_OK,
    summary="Получить информацию об услугах абонента.",
)
def get_services(
    account_id: int,
    uid: CurrentUid,
    service: ServiceServiceDep,
) -> Envelope[list]:
    """Return the list of services for the given account.

    Args:
        account_id: Path account id.
        uid: Authenticated user id.
        service: Injected :class:`ServiceService`.

    Returns:
        An :class:`Envelope` whose ``data`` is the service list.
    """
    return Envelope(success=True, data=service.get_services(uid, account_id), message="success", code=200)


@router.patch(
    "/subscriber/accounts/{account_id}/services/{service_id}",
    response_model=Envelope[None],
    status_code=status.HTTP_200_OK,
    summary="Смена тарифа; заблокировать/разблокировать услугу.",
)
def change_service(
    account_id: int,
    service_id: int,
    body: ChangeServiceRequest,
    uid: CurrentUid,
    service: ServiceServiceDep,
) -> Envelope[None]:
    """Apply a ``change-tariff`` / ``suspend`` / ``unsuspend`` action on a service.

    Args:
        account_id: Path account id.
        service_id: Path service id.
        body: Action payload.
        uid: Authenticated user id.
        service: Injected :class:`ServiceService`.

    Returns:
        An :class:`Envelope` describing the outcome.
    """
    result = service.change_service(
        uid, account_id, service_id, body.action,
        tariff_id=body.tariffId,
        date_start=body.date_start,
        date_end=body.date_end,
    )
    return Envelope(
        success=bool(result.get("success")),
        message=result.get("message", ""),
        code=int(result.get("code", 200)),
    )


@router.get(
    "/subscriber/accounts/{account_id}/services/{service_id}/additional-services",
    response_model=Envelope[list],
    status_code=status.HTTP_200_OK,
    summary="Получить дополнительные услуги.",
)
def get_additional_services(
    account_id: int,
    service_id: int,
    uid: CurrentUid,
    service: ServiceServiceDep,
) -> Envelope[list]:
    """Return the catalogue of additional services available for ``service_id``."""
    return Envelope(
        success=True,
        data=service.get_additional_services(uid, account_id, service_id),
        message="success",
        code=200,
    )


@router.patch(
    "/subscriber/accounts/{account_id}/services/{service_id}/"
    "additional-services/{additional_service_id}",
    response_model=Envelope[None],
    status_code=status.HTTP_200_OK,
    summary="Подключение/отключение дополнительных услуг.",
)
def set_additional_service(
    account_id: int,
    service_id: int,
    additional_service_id: int,
    body: ChangeAddServiceRequest,
    uid: CurrentUid,
    service: ServiceServiceDep,
) -> Envelope[None]:
    """Subscribe (``action == 1``) or unsubscribe (``action == 0``) an add-on."""
    result = service.set_additional_service(
        uid, account_id, service_id, additional_service_id, body.action
    )
    return Envelope(
        success=bool(result.get("success")),
        message=result.get("message", ""),
        code=int(result.get("code", 200)),
    )


__all__ = ["router"]
