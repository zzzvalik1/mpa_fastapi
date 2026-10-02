"""Схемы клиента / подписчика / аккаунта."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.common import Currency, RUB_CURRENCY


class PromisedPay(BaseModel):
    """Сводка обещанного платежа (обещанный платёж).

    Attributes:
        sum: Рекомендуемая сумма к оплате (``None``, если неприменимо).
        promised_until: ISO-дата, до которой исполняется обещание.
        status: Одно из значений: ``available``, ``unavailable``, ``expired``, ``taken``.
    """

    sum: float | None = Field(default=None, description="Рекомендуемая сумма.")
    promised_until: str | None = Field(default=None, description="Дата истечения обещания.")
    status: str = Field(..., description="Статус доступности обещания.")


class Balance(BaseModel):
    """Сводка баланса, встраиваемая в ответы аккаунта / подписчика."""

    total: float = Field(..., description="Текущий баланс.")
    recommended_pay: float | None = Field(default=None, description="Рекомендуемый платёж.")
    pay_until: str | None = Field(default=None, description="Крайний срок оплаты (ISO).")
    started_at: str | None = Field(default=None, description="Дата начала услуги.")
    ended_at: str | None = Field(default=None, description="Дата окончания услуги.")
    promised_pay: PromisedPay = Field(..., description="Сводка обещанного платежа.")
    currency: Currency = Field(default=RUB_CURRENCY, description="Информация о валюте.")


class SubscriberData(BaseModel):
    """Полезная нагрузка, возвращаемая ``GET /api/v1/subscriber``."""

    id: str = Field(..., description="Идентификатор пользователя (строковый).")
    code: str = Field(..., description="PIN подписчика.")
    first_name: str = Field("", description="Имя.")
    last_name: str = Field("", description="Фамилия.")
    active_account: "AccountData" = Field(..., description="Сводка активного аккаунта.")


class SuspendInfo(BaseModel):
    """Необязательная информация о приостановке / заморозке, прикрепляемая к аккаунтам."""

    suspend_from: str | None = Field(default=None, description="Дата начала заморозки.")
    suspend_to: str | None = Field(default=None, description="Дата окончания заморозки.")


class AccountData(BaseModel):
    """Полезная нагрузка аккаунта (используется как для одного аккаунта, так и для списков аккаунтов)."""

    id: str = Field(..., description="Идентификатор аккаунта (= user uid, строковый).")
    number: str = Field(..., description="PIN аккаунта.")
    suspend_allow: bool = Field(..., description="Разрешено ли действие приостановки.")
    balance: Balance = Field(..., description="Сводка баланса.")
    auto_payment: bool | None = Field(default=None, description="Флаг автоплатежа.")
    suspend_info: SuspendInfo = Field(default_factory=SuspendInfo, description="Информация о приостановке.")


class ChangeAccountRequest(BaseModel):
    """Тело ``PATCH /api/v1/subscriber/accounts/{accountId}``.

    Ровно один ``action`` обязателен; остальные поля условные.

    Attributes:
        action: Одно из значений: ``suspend``, ``unsuspend``, ``promised-pay``.
        date_start: Необязательная дата начала (для ``suspend``).
        date_end: Необязательная дата окончания (для ``suspend``).
    """

    action: Literal["suspend", "unsuspend", "promised-pay"]
    date_start: str | None = Field(default=None, description="Начало заморозки (YYYY-MM-DD).")
    date_end: str | None = Field(default=None, description="Конец заморозки (YYYY-MM-DD).")


class PayLinkData(BaseModel):
    """Полезная нагрузка, возвращаемая ``GET /pay-link``."""

    pay_link: str = Field(..., description="URL, который клиент должен открыть.")
    success_redirect_url: str = Field(..., description="URL редиректа при успехе.")
    failure_redirect_url: str = Field(..., description="URL редиректа при неудаче.")


class AutoPayLinkData(BaseModel):
    """Полезная нагрузка, возвращаемая ``GET /auto-payment-link``."""

    auto_payment_link: str = Field(
        ..., alias="auto-payment-link", description="URL автоплатежа."
    )
    success_redirect_url: str = Field(..., description="URL редиректа при успехе.")
    failure_redirect_url: str = Field(..., description="URL редиректа при неудаче.")

    model_config = {"populate_by_name": True}


class PromisedPayTermsData(BaseModel):
    """HTML-полезная нагрузка, возвращаемая ``GET /resources/promised-pay-terms``."""

    html: str = Field(..., description="HTML-содержимое, описывающее условия.")


# Разрешение прямой ссылки для ``SubscriberData.active_account``.
SubscriberData.model_rebuild()


__all__ = [
    "PromisedPay",
    "Balance",
    "SubscriberData",
    "SuspendInfo",
    "AccountData",
    "ChangeAccountRequest",
    "PayLinkData",
    "AutoPayLinkData",
    "PromisedPayTermsData",
]
