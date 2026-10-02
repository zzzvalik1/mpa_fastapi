"""Customer / subscriber / account schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.common import Currency, RUB_CURRENCY


class PromisedPay(BaseModel):
    """Promised-pay (обещанный платёж) summary.

    Attributes:
        sum: Recommended amount to pay (``None`` when N/A).
        promised_until: Iso date until which the promise is honoured.
        status: One of ``available``, ``unavailable``, ``expired``, ``taken``.
    """

    sum: float | None = Field(default=None, description="Recommended amount.")
    promised_until: str | None = Field(default=None, description="Promise expiry date.")
    status: str = Field(..., description="Promise availability status.")


class Balance(BaseModel):
    """Balance summary embedded in account / subscriber responses."""

    total: float = Field(..., description="Current balance.")
    recommended_pay: float | None = Field(default=None, description="Recommended payment.")
    pay_until: str | None = Field(default=None, description="Payment deadline (ISO).")
    started_at: str | None = Field(default=None, description="Service start date.")
    ended_at: str | None = Field(default=None, description="Service end date.")
    promised_pay: PromisedPay = Field(..., description="Promised-pay summary.")
    currency: Currency = Field(default=RUB_CURRENCY, description="Currency info.")


class SubscriberData(BaseModel):
    """Payload returned by ``GET /api/v1/subscriber``."""

    id: str = Field(..., description="User id (stringified).")
    code: str = Field(..., description="Subscriber PIN.")
    first_name: str = Field("", description="First name.")
    last_name: str = Field("", description="Last name.")
    active_account: "AccountData" = Field(..., description="Active account summary.")


class SuspendInfo(BaseModel):
    """Optional suspend / freeze info attached to accounts."""

    suspend_from: str | None = Field(default=None, description="Freeze start date.")
    suspend_to: str | None = Field(default=None, description="Freeze end date.")


class AccountData(BaseModel):
    """Account payload (used for both single account and account lists)."""

    id: str = Field(..., description="Account id (= user uid, stringified).")
    number: str = Field(..., description="Account PIN.")
    suspend_allow: bool = Field(..., description="Whether suspend action is allowed.")
    balance: Balance = Field(..., description="Balance summary.")
    auto_payment: bool | None = Field(default=None, description="Auto-payment flag.")
    suspend_info: SuspendInfo = Field(default_factory=SuspendInfo, description="Suspend info.")


class ChangeAccountRequest(BaseModel):
    """Body of ``PATCH /api/v1/subscriber/accounts/{accountId}``.

    Exactly one ``action`` is required; the other fields are conditional.

    Attributes:
        action: One of ``suspend``, ``unsuspend``, ``promised-pay``.
        date_start: Optional start date (for ``suspend``).
        date_end: Optional end date (for ``suspend``).
    """

    action: Literal["suspend", "unsuspend", "promised-pay"]
    date_start: str | None = Field(default=None, description="Freeze start (YYYY-MM-DD).")
    date_end: str | None = Field(default=None, description="Freeze end (YYYY-MM-DD).")


class PayLinkData(BaseModel):
    """Payload returned by ``GET /pay-link``."""

    pay_link: str = Field(..., description="URL the client should open.")
    success_redirect_url: str = Field(..., description="Success redirect URL.")
    failure_redirect_url: str = Field(..., description="Failure redirect URL.")


class AutoPayLinkData(BaseModel):
    """Payload returned by ``GET /auto-payment-link``."""

    auto_payment_link: str = Field(
        ..., alias="auto-payment-link", description="Auto-payment URL."
    )
    success_redirect_url: str = Field(..., description="Success redirect URL.")
    failure_redirect_url: str = Field(..., description="Failure redirect URL.")

    model_config = {"populate_by_name": True}


class PromisedPayTermsData(BaseModel):
    """HTML payload returned by ``GET /resources/promised-pay-terms``."""

    html: str = Field(..., description="HTML content describing the terms.")


# Resolve forward reference for ``SubscriberData.active_account``.
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
