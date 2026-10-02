"""Fee / transaction schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import Currency, RUB_CURRENCY


class Transaction(BaseModel):
    """Single transaction entry returned by ``POST .../transactions``."""

    date: str = Field(..., description="ISO-8601 transaction date.")
    debit: float = Field(..., description="Amount (positive = income, negative = expense).")
    currency: Currency = Field(default=RUB_CURRENCY, description="Currency info.")
    comment: str = Field(..., description="Human-readable comment.")


class TransactionsRequest(BaseModel):
    """Body of ``POST .../transactions``.

    Both fields are optional — when omitted, the API returns the full history.
    """

    start_date: str | None = Field(
        default=None, description="Inclusive lower bound (ISO-8601)."
    )
    end_date: str | None = Field(
        default=None, description="Inclusive upper bound (ISO-8601)."
    )


__all__ = ["Transaction", "TransactionsRequest"]
