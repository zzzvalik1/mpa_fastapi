"""Message / support-email schemas."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field, model_validator


class ShopRequest(BaseModel):
    """Body of ``POST /api/v1/subscriber/shop``.

    Attributes:
        goodId: Tariff id the user wants to order (0 if unknown).
        address: Customer address.
        phone_number: Customer phone.
        email: Customer email.
        comment: Free-text comment.
    """

    goodId: int = Field(default=0, ge=0, description="Target tariff id.")
    address: str = Field(default="", description="Customer address.")
    phone_number: str = Field(default="", description="Customer phone.")
    email: str = Field(default="", description="Customer email.")
    comment: str = Field(default="", description="Free-text comment.")


class SupportEmailRequest(BaseModel):
    """Body of ``POST /api/v1/support/send-email``.

    All fields are optional, but at least one of ``account`` / ``phone_number`` /
    ``email`` must be present so support can identify the customer.
    """

    account: str = Field(default="не указан", description="Subscriber PIN.")
    phone_number: str = Field(default="не указан", description="Customer phone.")
    email: str = Field(default="не указан", description="Customer email.")
    message: str = Field(..., min_length=1, description="Message body.")

    @model_validator(mode="after")
    def _ensure_contact(self) -> "SupportEmailRequest":
        """Validate that at least one contact field is non-default."""
        defaults = {"не указан"}
        contacts = {self.account, self.phone_number, self.email}
        if contacts.issubset(defaults):
            raise ValueError(
                "At least one of account / phone_number / email must be provided."
            )
        return self


__all__ = ["ShopRequest", "SupportEmailRequest"]
