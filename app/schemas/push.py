"""Схемы push-воркеров."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PushResult(BaseModel):
    """Универсальная полезная нагрузка результата, возвращаемая push-эндпоинтами."""

    success: bool = Field(..., description="Флаг успешности операции.")
    message: str = Field(..., description="Короткий человекочитаемый статус.")


__all__ = ["PushResult"]
