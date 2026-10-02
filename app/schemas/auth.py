"""Auth-related request / response schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """Body of ``POST /api/v1/auth/token``.

    Attributes:
        username: 6-digit PIN code (validated by length).
        password: Plain-text password (verified against bcrypt hash).
    """

    username: str = Field(
        ..., min_length=6, max_length=6, description="6-digit subscriber PIN code."
    )
    password: str = Field(..., min_length=1, description="Subscriber password.")


class LoginData(BaseModel):
    """Payload returned on successful login."""

    id: str = Field(..., description="User id (stringified, per the original API).")
    jwt: str = Field(..., description="Signed JWT token.")


class LogoutResponse(BaseModel):
    """Empty marker returned on logout — only the envelope matters."""

    pass


__all__ = ["LoginRequest", "LoginData", "LogoutResponse"]
