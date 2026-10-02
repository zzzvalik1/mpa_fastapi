"""HTTP client for the external mailer gateway.

Replaces the original PHP ``App/Helper/MailerSend.php`` (which used cURL).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import Settings, settings as _settings
from app.core.logging import get_logger


@dataclass(frozen=True, slots=True)
class MailResult:
    """Normalised result returned by :meth:`MailerClient.send_email`.

    Attributes:
        success: Whether the gateway reported success.
        message: Status / error message from the gateway.
        raw: The raw response body (string).
    """

    success: bool
    message: str
    raw: str


class MailerClient:
    """Thin sync wrapper around the external mailer HTTP gateway.

    The original PHP code POSTs a multipart-ish JSON payload to
    ``Settings.mail_url`` with the API key embedded.  We reproduce the
    contract using :mod:`httpx` (sync client) for easier testability.
    """

    def __init__(self, settings: Settings = _settings) -> None:
        """Initialise the client with application settings.

        Args:
            settings: Application settings (defaults to the global singleton).
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
        """Send a transactional email via the gateway.

        Args:
            sender: ``From`` address.
            to: ``To`` address.
            subject: Email subject.
            message: Email body (HTML).
            service: Gateway service name (default ``mlk_send_mail``).

        Returns:
            A :class:`MailResult` describing the outcome.
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
