"""Message service (mirrors ``App/Controller/MessageController.php``)."""

from __future__ import annotations

from typing import Any

from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.repositories.customer_repository import CustomerRepository
from app.repositories.tariff_repository import TariffRepository
from app.services.base_service import BaseService
from app.services.mailer_client import MailerClient


class MessageService(BaseService):
    """Handles shop-order requests and support-email submissions."""

    def __init__(
        self,
        customer_repo: CustomerRepository,
        service_repo,  # noqa: ANN001
        tariff_repo: TariffRepository,
        fee_repo,  # noqa: ANN001
        lklog_repo,  # noqa: ANN001
        webclientlog_repo,  # noqa: ANN001
        mailer: MailerClient,
        client_ip: str = "",
    ) -> None:
        """Initialise the service.

        Args:
            customer_repo: Customer repository.
            service_repo: Service repository (kept for API symmetry).
            tariff_repo: Tariff repository (used to look up the ordered tariff).
            fee_repo: Fee repository (unused here but kept for API symmetry).
            lklog_repo: LK-log repository.
            webclientlog_repo: Webclient-log repository.
            mailer: Mailer client.
            client_ip: IP of the calling client.
        """
        super().__init__(
            customer_repo=customer_repo,
            service_repo=service_repo,
            tariff_repo=tariff_repo,
            fee_repo=fee_repo,
            lklog_repo=lklog_repo,
            webclientlog_repo=webclientlog_repo,
            client_ip=client_ip,
        )
        self.mailer = mailer

    # ------------------------------------------------------------------ #
    # POST /subscriber/shop
    # ------------------------------------------------------------------ #
    def message_auth(
        self,
        uid: int | None,
        *,
        good_id: int,
        address: str,
        phone_number: str,
        email: str,
        comment: str,
    ) -> dict[str, Any]:
        """Send a shop-order email to support.

        Args:
            uid: Authenticated user id (``None`` for anonymous requests).
            good_id: Tariff id the user wants to order.
            address: Customer address.
            phone_number: Customer phone.
            email: Customer email.
            comment: Free-text comment.

        Returns:
            A dict ready to be embedded in the response envelope.
        """
        tariff = self.tariff_repo.get_tariff_by_tid(good_id) or {}
        if uid is None:
            self.logger.debug('Get query "/subscriber/message-non-auth".')
            body = (
                "Сообщение из мобильного приложения неавторизованного пользователя <br />"
                "---------------------------------------------------------------- <br />"
                f"Адрес: {address} <br />"
                f"Телефон: {phone_number} <br />"
                f"Email: {email} <br />"
                f"Заказал ТП :{tariff.get('name')} стоимостью {tariff.get('abonent_fee')} руб. [tid {good_id}]<br />"
                f"Комментарий: Добрый день! Хочу сделать заказ: {comment} <br />"
            )
            self.mailer.send_email(
                sender="messaging@starlink.ru",
                to="support@starlink.ru",
                subject="Сообщение из мобильного приложения неавторизованного пользователя",
                message=body,
            )
            return {
                "data": (
                    "Добрый день! \nХочу сделать заказ \nМои данные: \n"
                    f" Адрес: {address}\n Логин: {email}\n Телефон: {phone_number}\n"
                    f" Комментарий: {comment}\n"
                ),
            }

        user = self.customer_repo.find_subscriber_by_uid(uid)
        if not user:
            raise NotFoundError("incorrect username")
        self.logger.debug('User of id: %s get query "/subscriber/message-auth".', uid)
        body = (
            f'Клиент <a href="https://client.starlink.ru/showuser/{uid}.html">'
            f"https://client.starlink.ru/showuser/{uid}.html</a> <br />"
            "---------------------------------------------------------------- <br />"
            f"ПИН: {user.get('pin')} <br />"
            f"Логин: {user.get('login')} <br />"
            f"Адрес: {address} <br />"
            f"Телефон: {phone_number} <br />"
            f"Email: {email} <br />"
            f"Заказал ТП :{tariff.get('name')} стоимостью {tariff.get('abonent_fee')} руб. [tid {good_id}]<br />"
            f"Комментарий: Добрый день! Хочу сделать заказ: {comment} <br />"
        )
        result = self.mailer.send_email(
            sender="messaging@starlink.ru",
            to="support@starlink.ru",
            subject=f"Сообщение из мобильного приложения авторизованного пользователя {user.get('pin')}",
            message=body,
        )
        self.logger.info("Send email to: support@starlink.ru. Result: %s", result.message)
        return {
            "data": (
                "Добрый день! \nХочу сделать заказ \nМои данные: \n"
                f"ПИН: {user.get('pin')}\n Логин: {user.get('login')}\n"
                f" Телефон: {phone_number}\n Комментарий: {comment}\n"
            ),
        }

    # ------------------------------------------------------------------ #
    # POST /support/send-email
    # ------------------------------------------------------------------ #
    def send_support_email(
        self,
        *,
        account: str,
        phone_number: str,
        email: str,
        message: str,
    ) -> dict[str, Any]:
        """Send a support email.

        Args:
            account: Subscriber PIN (or ``"не указан"``).
            phone_number: Customer phone.
            email: Customer email.
            message: Message body.

        Returns:
            A dict with ``success`` / ``message`` / ``code`` keys.
        """
        self.logger.debug('User of pin: %s get query "/support/send-email".', account)

        if account and account != "не указан":
            user = self.customer_repo.find_customer_by_pin(account)
            if user and user.get("uid"):
                subject = (
                    f"Сообщение из мобильного приложения авторизованного пользователя {user.get('pin')}"
                )
                body = (
                    f'Клиент <a href="https://client.starlink.ru/showuser/{user["uid"]}.html">'
                    f"https://client.starlink.ru/showuser/{user['uid']}.html</a> <br />"
                )
            else:
                self.logger.error("User of pin: %s not found.", account)
                subject = "Сообщение из мобильного приложения неавторизованного пользователя"
                body = "<b>Сообщение из мобильного приложения неавторизованного пользователя</b><br />"
        else:
            subject = "Сообщение из мобильного приложения неавторизованного пользователя"
            body = "<b>Сообщение из мобильного приложения неавторизованного пользователя</b><br />"

        body += (
            "------------------------------------------------------------------------------- <br /><br />"
            f"ПИН: {account} <br />"
            f"Телефон: {phone_number} <br />"
            f"Email: {email} <br />"
            f"Сообщение: {message} <br />"
        )
        result = self.mailer.send_email(
            sender="messaging@starlink.ru",
            to="support@starlink.ru",
            subject=subject,
            message=body,
        )
        self.logger.info("Send email to: support@starlink.ru. Result: %s", result.message)
        return {
            "success": result.success,
            "message": "email sended" if result.success else "email not send",
            "code": 200,
        }


__all__ = ["MessageService"]
