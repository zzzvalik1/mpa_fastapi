"""Common, reusable response schemas.

The mobile application expects every endpoint to return the same envelope::

    {
        "success": true|false,
        "message": "success",
        "code": 200,
        "data": <payload>
    }

The :class:`Envelope` generic below models this contract and is used as the
default ``response_model`` for every endpoint.  Specialised schemas (in this
package) describe the shape of ``data``.
"""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field


T = TypeVar("T")


class Envelope(BaseModel, Generic[T]):
    """Canonical API response envelope.

    Attributes:
        success: ``True`` for successful responses, ``False`` for errors.
        message: Short human-readable status text.
        code: HTTP-style status code (mirrors the real HTTP status).
        data: Optional payload; type is parameterised.
    """

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    success: bool = Field(..., description="Operation success flag.")
    message: str = Field("success", description="Short human-readable status.")
    code: int = Field(200, ge=100, le=599, description="HTTP-style status code.")
    data: T | None = Field(default=None, description="Optional payload.")


class Currency(BaseModel):
    """Currency metadata embedded in balance / price objects."""

    id: int = Field(..., description="Internal currency id.")
    code: str = Field(..., description="ISO-4217 currency code, e.g. ``RUB``.")
    title: str = Field(..., description="Human-readable currency title.")


#: Pre-shared currency instance for RUB.
RUB_CURRENCY: Currency = Currency(id=1044, code="RUB", title="Руб")


class ErrorEnvelope(BaseModel):
    """Canonical error envelope (used by exception handlers)."""

    success: bool = Field(False, description="Always ``false`` for errors.")
    message: str = Field(..., description="Error message.")
    code: int = Field(..., description="HTTP status code.")


__all__ = ["Envelope", "Currency", "RUB_CURRENCY", "ErrorEnvelope"]
