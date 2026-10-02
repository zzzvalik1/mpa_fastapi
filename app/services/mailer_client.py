"""HTTP-клиент внешнего mailer-шлюза.

Заменяет исходный PHP-класс ``App/Helper/MailerSend.php`` (который использовал cURL).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import Settings, settings as _settings
from app.core.logging import get_logger


@dataclass(frozen=True, slots=True)
class MailResult:
    """Нормализованный результат, возвращаемый :meth:`MailerClient.send_email`.

    Attributes:
        success: Успех по отчёту шлюза.
        message: Статус / сообщение об ошибке от шлюза.
        raw: Сырой body-ответ (string).
    """

    success: bool
    message: str
    raw: str


class MailerClient:
    """Тонкий sync-обвертка вокруг внешнего mailer HTTP-шлюза.

    Исходный PHP-код отправляет multipart-подобный JSON-payload на
    ``Settings.mail_url`` с встроенным API-ключом.  Мы воспроизводим
    контракт с помощью :mod:`httpx` (sync-клиент) для удобства тестирования.
    """

    def __init__(self, settings: Settings = _settings) -> None:
        """Инициализирует клиент настройками приложения.

        Args:
            settings: Настройки приложения (по умолчанию — глобальный singleton).
        """
        self._settings = settings
        self._logger = get_logger()
        self._url = settings.mail_url
        self._api_key = settings.mail_key

    def send_email(
        self,
        *,
        sender: str,
        to: str,
        subject: str,
        message: str,
        service: str = "mlk_send_mail",
    ) -> MailResult:
        """Отправляет транзакционный email через шлюз.

        Args:
            sender: Адрес ``From``.
            to: Адрес ``To``.
            subject: Тема email.
            message: Тело email (HTML).
            service: Имя сервиса шлюза (по умолчанию ``mlk_send_mail``).

        Returns:
            :class:`MailResult`, описывающий результат.
        """
        payload_data = {
            "from": sender,
            "to": to,
            "subject": subject,
            "message": message,
            "service": service,
        }
        # The PHP version sends a multipart form with two fields:
        #   data    -> JSON-encoded email payload
        #   apiKey  -> shared secret
        form_data = {
            "data": __import__("json").dumps(payload_data, ensure_ascii=False),
            "apiKey": self._api_key,
        }

        try:
            response = httpx.post(
                self._url,
                data=form_data,
                timeout=30.0,
                verify=False,  # mirror PHP's CURLOPT_SSL_VERIFYPEER = 0
            )
        except httpx.HTTPError as exc:
            self._logger.error("Mailer HTTP error: %s", exc)
            return MailResult(success=False, message=f"HTTP error: {exc}", raw="")

        raw_text = response.text
        try:
            parsed = response.json()
            message = str(parsed.get("message") or raw_text)
            success = bool(parsed.get("success", True))
        except Exception:  # noqa: BLE001 — non-JSON response
            parsed = None
            message = raw_text
            success = False

        if parsed is None and response.is_success:
            success = True

        return MailResult(success=success, message=message, raw=raw_text)


__all__ = ["MailerClient", "MailResult"]
