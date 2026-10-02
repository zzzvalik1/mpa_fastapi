"""Схемы сообщений и писем в поддержку."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field, model_validator


class ShopRequest(BaseModel):
    """Тело ``POST /api/v1/subscriber/shop``.

    Attributes:
        goodId: Идентификатор тарифа, который хочет заказать пользователь (0, если неизвестно).
        address: Адрес клиента.
        phone_number: Телефон клиента.
        email: Email клиента.
        comment: Произвольный текстовый комментарий.
    """

    goodId: int = Field(default=0, ge=0, description="Идентификатор целевого тарифа.")
    address: str = Field(default="", description="Адрес клиента.")
    phone_number: str = Field(default="", description="Телефон клиента.")
    email: str = Field(default="", description="Электронная почта клиента.")
    comment: str = Field(default="", description="Произвольный текстовый комментарий.")


class SupportEmailRequest(BaseModel):
    """Тело ``POST /api/v1/support/send-email``.

    Все поля необязательны, но хотя бы одно из ``account`` / ``phone_number`` /
    ``email`` должно присутствовать, чтобы поддержка могла идентифицировать клиента.
    """

    account: str = Field(default="не указан", description="PIN подписчика.")
    phone_number: str = Field(default="не указан", description="Телефон клиента.")
    email: str = Field(default="не указан", description="Электронная почта клиента.")
    message: str = Field(..., min_length=1, description="Тело сообщения.")

    @model_validator(mode="after")
    def _ensure_contact(self) -> "SupportEmailRequest":
        """Проверка, что хотя бы одно контактное поле не является значением по умолчанию."""
        defaults = {"не указан"}
        contacts = {self.account, self.phone_number, self.email}
        if contacts.issubset(defaults):
            raise ValueError(
                "At least one of account / phone_number / email must be provided."
            )
        return self


__all__ = ["ShopRequest", "SupportEmailRequest"]
