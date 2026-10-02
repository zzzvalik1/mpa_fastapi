"""Схемы услуг и дополнительных услуг."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.common import Currency, RUB_CURRENCY


class ServiceState(BaseModel):
    """Блок статуса, встраиваемый в каждый объект услуги."""

    id: int = Field(..., description="Числовой идентификатор статуса (1 = unlock, 2 = lock, ...).")
    code: Literal["unlock", "lock"] = Field(..., description="Человекочитаемый код.")
    title: str = Field(..., description="Локализованное название статуса.")
    paused: bool = Field(..., description="Приостановлена ли услуга.")


class Price(BaseModel):
    """Блок цены, общий для услуг, дополнительных услуг и тарифов."""

    total: float = Field(..., description="Сумма в локальной валюте.")
    currency: Currency = Field(default=RUB_CURRENCY, description="Информация о валюте.")
    frequency: str = Field(..., description="Частота биллинга, например ``month`` / ``daytime``.")


class ServiceInfo(BaseModel):
    """Необязательный описательный блок информации (например, скорость)."""

    type: str = Field(..., description="Тип информации, например ``speed`` или ``description``.")
    title: str = Field(..., description="Заголовок, отображаемый пользователю.")
    description: str | None = Field(default=None, description="Текст описания.")


class AdditionalService(BaseModel):
    """Запись дополнительной (дочерней) услуги."""

    id: int = Field(..., description="Идентификатор услуги (sid).")
    title: str = Field(..., description="Название услуги.")
    description: str | None = Field(default=None, description="Описание услуги.")
    pay_until: str | None = Field(default=None, description="Крайний срок оплаты (ISO).")
    ended_at: str | None = Field(default=None, description="Дата окончания услуги.")
    info: ServiceInfo | None = Field(default=None, description="Необязательный блок информации.")
    type: str | None = Field(default=None, description="Идентификатор типа услуги (slug).")
    type_add_service: str | None = Field(default=None, description="``auto`` или ``manual``.")
    price: Price = Field(..., description="Блок цены.")
    state: ServiceState = Field(..., description="Блок состояния.")
    mutations: list[str] = Field(default_factory=list, description="Разрешённые мутации.")


class NextService(BaseModel):
    """Запись запланированной (следующей) услуги, отображаемая при ожидаемой смене тарифа."""

    id: int = Field(..., description="Идентификатор услуги (sid).")
    title: str = Field(..., description="Название тарифа.")
    info: ServiceInfo | None = Field(default=None, description="Блок информации.")
    description: str | None = Field(default=None, description="Описание типа тарифа.")
    started_at: str | None = Field(default=None, description="Дата активации.")
    price: Price = Field(..., description="Блок цены.")
    state: ServiceState = Field(..., description="Блок состояния.")
    address: str = Field("", description="Адрес услуги.")
    mutations: list[str] = Field(default_factory=list, description="Разрешённые мутации.")


class Service(BaseModel):
    """Основная запись услуги, возвращаемая ``GET .../services``."""

    id: int = Field(..., description="Идентификатор услуги (sid).")
    title: str = Field(..., description="Название тарифа.")
    info: ServiceInfo | None = Field(default=None, description="Блок информации.")
    description: str | None = Field(default=None, description="Описание типа тарифа.")
    pay_until: str | None = Field(default=None, description="Крайний срок оплаты.")
    type: str | None = Field(default=None, description="Идентификатор типа услуги (slug).")
    price: Price = Field(..., description="Блок цены.")
    state: ServiceState = Field(..., description="Блок состояния.")
    next: NextService | list[NextService] | None = Field(
        default=None, description="Запланированная следующая услуга(и)."
    )
    address: str = Field("", description="Адрес услуги.")
    additional_services: list[AdditionalService] = Field(
        default_factory=list, description="Активные дополнительные услуги."
    )
    mutations: list[str] = Field(default_factory=list, description="Разрешённые мутации.")


class ChangeServiceRequest(BaseModel):
    """Тело ``PATCH .../services/{serviceId}``.

    Attributes:
        action: Одно из значений: ``change-tariff``, ``suspend``, ``unsuspend``.
        tariffId: Обязательно, когда ``action == "change-tariff"``.
        date_start: Обязательно, когда ``action == "suspend"``.
        date_end: Обязательно, когда ``action == "suspend"``.
    """

    action: Literal["change-tariff", "suspend", "unsuspend"]
    tariffId: int | None = Field(default=None, description="Идентификатор целевого тарифа.")
    date_start: str | None = Field(default=None, description="Дата начала заморозки.")
    date_end: str | None = Field(default=None, description="Дата окончания заморозки.")


class ChangeAddServiceRequest(BaseModel):
    """Тело ``PATCH .../additional-services/{AdditionalServiceId}``.

    ``action`` — целое число в оригинальном API (0 = отписка, 1 = подписка).
    """

    action: Literal[0, 1] = Field(..., description="0 = отписка, 1 = подписка.")


__all__ = [
    "ServiceState",
    "Price",
    "ServiceInfo",
    "AdditionalService",
    "NextService",
    "Service",
    "ChangeServiceRequest",
    "ChangeAddServiceRequest",
]
