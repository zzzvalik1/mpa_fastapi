"""Общие переиспользуемые схемы ответов.

Мобильное приложение ожидает, что каждый эндпоинт возвращает один и тот же
конверт::

    {
        "success": true|false,
        "message": "success",
        "code": 200,
        "data": <payload>
    }

Дженерик :class:`Envelope` ниже моделирует этот контракт и используется как
``response_model`` по умолчанию для каждого эндпоинта.  Специализированные
схемы (в этом пакете) описывают структуру ``data``.
"""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field


T = TypeVar("T")


class Envelope(BaseModel, Generic[T]):
    """Канонический конверт ответа API.

    Attributes:
        success: ``True`` для успешных ответов, ``False`` для ошибок.
        message: Короткий человекочитаемый текст статуса.
        code: Код статуса в стиле HTTP (зеркалирует реальный HTTP-статус).
        data: Необязательная полезная нагрузка; тип параметризован.
    """

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    success: bool = Field(..., description="Флаг успешности операции.")
    message: str = Field("success", description="Короткий человекочитаемый статус.")
    code: int = Field(200, ge=100, le=599, description="Код статуса в стиле HTTP.")
    data: T | None = Field(default=None, description="Необязательная полезная нагрузка.")


class Currency(BaseModel):
    """Метаданные валюты, встраиваемые в объекты баланса / цены."""

    id: int = Field(..., description="Внутренний идентификатор валюты.")
    code: str = Field(..., description="Код валюты ISO-4217, например ``RUB``.")
    title: str = Field(..., description="Человекочитаемое название валюты.")


#: Предзаготовленный экземпляр валюты для RUB.
RUB_CURRENCY: Currency = Currency(id=1044, code="RUB", title="Руб")


class ErrorEnvelope(BaseModel):
    """Канонический конверт ошибки (используется обработчиками исключений)."""

    success: bool = Field(False, description="Всегда ``false`` для ошибок.")
    message: str = Field(..., description="Сообщение об ошибке.")
    code: int = Field(..., description="HTTP-код статуса.")


__all__ = ["Envelope", "Currency", "RUB_CURRENCY", "ErrorEnvelope"]
