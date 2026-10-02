"""Схемы запросов / ответов для аутентификации."""

from __future__ import annotations

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """Тело ``POST /api/v1/auth/token``.

    Attributes:
        username: 6-значный PIN-код (проверяется по длине).
        password: Пароль в открытом виде (проверяется против bcrypt-хеша).
    """

    username: str = Field(
        ..., min_length=6, max_length=6, description="6-значный PIN-код подписчика."
    )
    password: str = Field(..., min_length=1, description="Пароль подписчика.")


class LoginData(BaseModel):
    """Полезная нагрузка, возвращаемая при успешном входе."""

    id: str = Field(..., description="Идентификатор пользователя (строковый, согласно оригинальному API).")
    jwt: str = Field(..., description="Подписанный JWT-токен.")


class LogoutResponse(BaseModel):
    """Пустой маркер, возвращаемый при выходе — важен только конверт."""

    pass


__all__ = ["LoginRequest", "LoginData", "LogoutResponse"]
