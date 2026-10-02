"""Схемы тарифов."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.common import Currency, RUB_CURRENCY


class TariffPrice(BaseModel):
    """Блок цены для записи тарифа."""

    total: float = Field(..., description="Ежемесячная плата.")
    currency: Currency = Field(default=RUB_CURRENCY, description="Информация о валюте.")
    frequency: str = Field(..., description="Частота биллинга.")


class Tariff(BaseModel):
    """Запись тарифа, возвращаемая ``GET .../tariffs``."""

    id: int = Field(..., description="Идентификатор тарифа (tid).")
    title: str = Field(..., description="Название тарифа.")
    price: TariffPrice = Field(..., description="Блок цены.")
    started_at: str | None = Field(default=None, description="Дата активации (ISO).")


__all__ = ["TariffPrice", "Tariff"]
