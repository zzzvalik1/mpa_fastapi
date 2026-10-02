"""Схемы платежей / транзакций."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import Currency, RUB_CURRENCY


class Transaction(BaseModel):
    """Запись одной транзакции, возвращаемая ``POST .../transactions``."""

    date: str = Field(..., description="Дата транзакции ISO-8601.")
    debit: float = Field(..., description="Сумма (положительная = доход, отрицательная = расход).")
    currency: Currency = Field(default=RUB_CURRENCY, description="Информация о валюте.")
    comment: str = Field(..., description="Человекочитаемый комментарий.")


class TransactionsRequest(BaseModel):
    """Тело ``POST .../transactions``.

    Оба поля необязательны — при отсутствии API возвращает полную историю.
    """

    start_date: str | None = Field(
        default=None, description="Включающая нижняя граница (ISO-8601)."
    )
    end_date: str | None = Field(
        default=None, description="Включающая верхняя граница (ISO-8601)."
    )


__all__ = ["Transaction", "TransactionsRequest"]
