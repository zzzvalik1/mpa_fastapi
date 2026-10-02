"""Tariff schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.common import Currency, RUB_CURRENCY


class TariffPrice(BaseModel):
    """Price block for a tariff entry."""

    total: float = Field(..., description="Monthly fee.")
    currency: Currency = Field(default=RUB_CURRENCY, description="Currency info.")
    frequency: str = Field(..., description="Billing frequency.")


class Tariff(BaseModel):
    """Tariff entry returned by ``GET .../tariffs``."""

    id: int = Field(..., description="Tariff id (tid).")
    title: str = Field(..., description="Tariff name.")
    price: TariffPrice = Field(..., description="Price block.")
    started_at: str | None = Field(default=None, description="Activation date (ISO).")


__all__ = ["TariffPrice", "Tariff"]
