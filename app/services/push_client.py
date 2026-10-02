"""HTTP client for the external push-notification gateway.

Replaces the original PHP ``App/Helper/PushSend.php`` (cURL based).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import httpx

from app.core.config import Settings, settings as _settings
from app.core.logging import get_logger


@dataclass(frozen=True, slots=True)
class PushResultData:
    """Normalised result returned by :meth:`PushClient.send_push`.

    Attributes:
        success: Whether the gateway reported success.
        message: Status / error message.
        data:    Parsed JSON payload (dict) when the response was JSON.
    """

    success: bool
    message: str
    data: dict[str, Any] | list[Any] | None = field(default=None)


class PushClient:
    """Thin sync wrapper around the external push-notification HTTP gateway."""

    def __init__(self, settings: Settings = _settings) -> None:
        """Initialise the client.

        Args:
            settings: Application settings (defaults to the global singleton).
        """
        self._settings = settings
        self._logger = get_logger()
        self._base_url = settings.push_url.rstrip("/")
        self._api_key = settings.push_key

    def _headers(self) -> dict[str, str]:
        """Return the standard Bearer-auth + JSON headers."""
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    def send_push(
        self,
        path: str,
        data: dict[str, Any] | None = None,
        method: str = "GET",
    ) -> PushResultData:
        """Send a request to the push gateway.

        Args:
            path: Path appended to :attr:`Settings.push_url` (must start with ``/``).
            data: Optional JSON body (used for POST).
            method: HTTP method (``"GET"`` or ``"POST"``).

        Returns:
            A :class:`PushResultData` with the parsed response.
        """
        url = f"{self._base_url}{path}"
        try:
            if method.upper() == "POST":
                response = httpx.post(
                    url,
                    json=data,
                    headers=self._headers(),
                    timeout=60.0,
                    verify=False,
                )
            else:
                response = httpx.get(
                    url,
                    headers=self._headers(),
                    timeout=60.0,
                    verify=False,
                )
        except httpx.HTTPError as exc:
            self._logger.error("Push HTTP error: %s", exc)
            return PushResultData(success=False, message=f"HTTP error: {exc}")

        raw = response.text
        try:
            parsed = response.json()
        except Exception:  # noqa: BLE001
            return PushResultData(success=False, message=raw or "invalid JSON")

        success = bool(parsed.get("success", False)) if isinstance(parsed, dict) else False
        message = str(parsed.get("message", "")) if isinstance(parsed, dict) else raw
        return PushResultData(success=success, message=message, data=parsed)

    def get_auth_users(self, path: str = "/statistics/active-subscribers") -> list[int]:
        """Return the list of currently authenticated subscriber uids.

        Args:
            path: Endpoint path (default ``/statistics/active-subscribers``).

        Returns:
            A list of integer uids (empty list on failure).
        """
        result = self.send_push(path, method="GET")
        if not result.success or not isinstance(result.data, dict):
            return []
        data = result.data.get("data") or []
        if not isinstance(data, list):
            return []
        uids: list[int] = []
        for item in data:
            if isinstance(item, dict) and "subscriber_code" in item:
                try:
                    uids.append(int(item["subscriber_code"]))
                except (TypeError, ValueError):
                    continue
        return uids


__all__ = ["PushClient", "PushResultData"]
