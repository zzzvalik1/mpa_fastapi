"""Service / additional-service schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.common import Currency, RUB_CURRENCY


class ServiceState(BaseModel):
    """Status block embedded in every service object."""

    id: int = Field(..., description="Numeric status id (1 = unlock, 2 = lock, ...).")
    code: Literal["unlock", "lock"] = Field(..., description="Human-readable code.")
    title: str = Field(..., description="Localised status title.")
    paused: bool = Field(..., description="Whether the service is paused.")


class Price(BaseModel):
    """Price block shared by services, additional services and tariffs."""

    total: float = Field(..., description="Amount in the local currency.")
    currency: Currency = Field(default=RUB_CURRENCY, description="Currency info.")
    frequency: str = Field(..., description="Billing frequency, e.g. ``month`` / ``daytime``.")


class ServiceInfo(BaseModel):
    """Optional descriptive info block (e.g. speed)."""

    type: str = Field(..., description="Info type, e.g. ``speed`` or ``description``.")
    title: str = Field(..., description="Title shown to the user.")
    description: str | None = Field(default=None, description="Description text.")


class AdditionalService(BaseModel):
    """Additional (child) service entry."""

    id: int = Field(..., description="Service id (sid).")
    title: str = Field(..., description="Service title.")
    description: str | None = Field(default=None, description="Service description.")
    pay_until: str | None = Field(default=None, description="Payment deadline (ISO).")
    ended_at: str | None = Field(default=None, description="Service end date.")
    info: ServiceInfo | None = Field(default=None, description="Optional info block.")
    type: str | None = Field(default=None, description="Service type slug.")
    type_add_service: str | None = Field(default=None, description="``auto`` or ``manual``.")
    price: Price = Field(..., description="Price block.")
    state: ServiceState = Field(..., description="State block.")
    mutations: list[str] = Field(default_factory=list, description="Allowed mutations.")


class NextService(BaseModel):
    """Scheduled (next) service entry, shown when a tariff change is pending."""

    id: int = Field(..., description="Service id (sid).")
    title: str = Field(..., description="Tariff name.")
    info: ServiceInfo | None = Field(default=None, description="Info block.")
    description: str | None = Field(default=None, description="Tariff type description.")
    started_at: str | None = Field(default=None, description="Activation date.")
    price: Price = Field(..., description="Price block.")
    state: ServiceState = Field(..., description="State block.")
    address: str = Field("", description="Service address.")
    mutations: list[str] = Field(default_factory=list, description="Allowed mutations.")


class Service(BaseModel):
    """Primary service entry returned by ``GET .../services``."""

    id: int = Field(..., description="Service id (sid).")
    title: str = Field(..., description="Tariff name.")
    info: ServiceInfo | None = Field(default=None, description="Info block.")
    description: str | None = Field(default=None, description="Tariff type description.")
    pay_until: str | None = Field(default=None, description="Payment deadline.")
    type: str | None = Field(default=None, description="Service type slug.")
    price: Price = Field(..., description="Price block.")
    state: ServiceState = Field(..., description="State block.")
    next: NextService | list[NextService] | None = Field(
        default=None, description="Scheduled next service(s)."
    )
    address: str = Field("", description="Service address.")
    additional_services: list[AdditionalService] = Field(
        default_factory=list, description="Active additional services."
    )
    mutations: list[str] = Field(default_factory=list, description="Allowed mutations.")


class ChangeServiceRequest(BaseModel):
    """Body of ``PATCH .../services/{serviceId}``.

    Attributes:
        action: One of ``change-tariff``, ``suspend``, ``unsuspend``.
        tariffId: Required when ``action == "change-tariff"``.
        date_start: Required when ``action == "suspend"``.
        date_end: Required when ``action == "suspend"``.
    """

    action: Literal["change-tariff", "suspend", "unsuspend"]
    tariffId: int | None = Field(default=None, description="Target tariff id.")
    date_start: str | None = Field(default=None, description="Freeze start date.")
    date_end: str | None = Field(default=None, description="Freeze end date.")


class ChangeAddServiceRequest(BaseModel):
    """Body of ``PATCH .../additional-services/{AdditionalServiceId}``.

    ``action`` is an integer in the original API (0 = unsubscribe, 1 = subscribe).
    """

    action: Literal[0, 1] = Field(..., description="0 = unsubscribe, 1 = subscribe.")


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
