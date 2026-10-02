"""Эндпоинты услуг (группа ``/subscriber/accounts/{account_id}/services``)."""

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
    """Вернуть список услуг для указанного аккаунта.

    Args:
        account_id: id аккаунта из пути.
        uid: id аутентифицированного пользователя.
        service: Внедрённый :class:`ServiceService`.

    Returns:
        :class:`Envelope`, у которого ``data`` — список услуг.
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
    """Применить действие ``change-tariff`` / ``suspend`` / ``unsuspend`` к услуге.

    Args:
        account_id: id аккаунта из пути.
        service_id: id услуги из пути.
        body: Полезная нагрузка действия.
        uid: id аутентифицированного пользователя.
        service: Внедрённый :class:`ServiceService`.

    Returns:
        :class:`Envelope`, описывающий результат.
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
    """Вернуть каталог дополнительных услуг, доступных для ``service_id``."""
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
    """Подключить (``action == 1``) или отключить (``action == 0``) доп. услугу."""
    result = service.set_additional_service(
        uid, account_id, service_id, additional_service_id, body.action
    )
    return Envelope(
        success=bool(result.get("success")),
        message=result.get("message", ""),
        code=int(result.get("code", 200)),
    )


__all__ = ["router"]
