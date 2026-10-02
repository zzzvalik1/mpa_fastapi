"""Push-notification worker schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PushResult(BaseModel):
    """Generic result payload returned by the push endpoints."""

    success: bool = Field(..., description="Operation success flag.")
    message: str = Field(..., description="Short human-readable status.")


__all__ = ["PushResult"]
