"""HTTP-клиент внешнего push-шлюза.

Заменяет исходный PHP-класс ``App/Helper/PushSend.php`` (на cURL).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import httpx

from app.core.config import Settings, settings as _settings
from app.core.logging import get_logger


@dataclass(frozen=True, slots=True)
class PushResultData:
    """Нормализованный результат, возвращаемый :meth:`PushClient.send_push`.

    Attributes:
        success: Успех по отчёту шлюза.
        message: Статус / сообщение об ошибке.
        data:    Разобранный JSON-payload (dict), если ответ был JSON.
    """

    success: bool
    message: str
    data: dict[str, Any] | list[Any] | None = field(default=None)


class PushClient:
    """Тонкая sync-обвертка вокруг внешнего push-HTTP-шлюза."""

    def __init__(self, settings: Settings = _settings) -> None:
        """Инициализирует клиент.

        Args:
            settings: Настройки приложения (по умолчанию — глобальный singleton).
        """
        self._settings = settings
        self._logger = get_logger()
        self._base_url = settings.push_url.rstrip("/")
        self._api_key = settings.push_key

    def _headers(self) -> dict[str, str]:
        """Возвращает стандартные заголовки Bearer-auth + JSON."""
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
        """Отправляет запрос на push-шлюз.

        Args:
            path: Путь, добавляемый к :attr:`Settings.push_url` (должен начинаться с ``/``).
            data: Опциональное JSON-тело (используется для POST).
            method: HTTP-метод (``"GET"`` или ``"POST"``).

        Returns:
            :class:`PushResultData` с разобранным ответом.
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
        """Возвращает список uid’ов текущих аутентифицированных абонентов.

        Args:
            path: Путь эндпоинта (по умолчанию ``/statistics/active-subscribers``).

        Returns:
            Список целых uid (пустой список при ошибке).
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
