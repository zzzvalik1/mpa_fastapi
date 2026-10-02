"""Push service (mirrors ``App/Controller/PushController.php``).

The push endpoints are cron-style workers:

* ``GET /notifications/send``       — flush waiting push messages.
* ``GET /notifications/status``      — refresh status of recent pushes.
* ``GET /notifications/status-old``  — refresh status of long-pending pushes.

The original PHP implementation used ``shell_exec`` + ``ps`` to enforce
single-flight; here we use a process-wide :class:`threading.Lock` which is
sufficient inside a single-process uvicorn worker (the recommended
deployment mode for these endpoints).
"""

from __future__ import annotations

import threading
from datetime import datetime
from typing import Any

from app.core.logging import get_push_logger
from app.repositories.push_repository import PushRepository
from app.services.push_client import PushClient


class PushService:
    """Worker service for the push-notification endpoints."""

    def __init__(self, push_repo: PushRepository, push_client: PushClient) -> None:
        """Initialise the service.

        Args:
            push_repo: Push repository (main DB).
            push_client: Push HTTP client.
        """
        self.push_repo = push_repo
        self.push_client = push_client
        self.logger = get_push_logger()
        # Single-flight lock — prevents overlapping runs within one process.
        self._send_lock = threading.Lock()
        self._status_lock = threading.Lock()
        self._status_old_lock = threading.Lock()

    # ------------------------------------------------------------------ #
    # GET /notifications/send
    # ------------------------------------------------------------------ #
    def send_messages(self) -> dict[str, Any]:
        """Send all waiting push messages.

        Returns:
            A dict with ``success`` / ``message`` / ``code`` keys.
        """
        if not self._send_lock.acquire(blocking=False):
            self.logger.error("== /notifications/send already running — skipping. ==")
            return {"success": True, "message": "already running", "code": 200}
        try:
            active_users = self.push_client.get_auth_users()
            messages = self.push_repo.get_wait_messages()
            if not messages:
                self.logger.info("---- Нет записей для отправки ----")
                return {"success": True, "message": "Нет записей для отправки.", "code": 200}

            for item in messages:
                update_data: dict[str, Any] = {}
                uid = int(item.get("uid") or 0)
                if uid in active_users:
                    send_data = {
                        "subscriber": str(uid),
                        "title": item.get("subject"),
                        "body": item.get("message"),
                        "data": {"type": item.get("type")},
                    }
                    response = self.push_client.send_push(
                        "/notifications/send", data=send_data, method="POST"
                    )
                    if response.success and isinstance(response.data, dict):
                        data_arr = response.data.get("data") or []
                        first = data_arr[0] if isinstance(data_arr, list) and data_arr else {}
                        if isinstance(first, dict):
                            update_data["mlk_id"] = first.get("id")
                            update_data["status"] = first.get("status")
                            update_data["deliver_time"] = first.get("created_at")
                            self.logger.info(
                                "Отправка сообщения %s на uid:%s.",
                                first.get("id"), uid,
                            )
                        else:
                            update_data["comment"] = response.message or "unknown error"
                            update_data["status"] = "error"
                    else:
                        update_data["comment"] = response.message or "unknown error"
                        update_data["status"] = "error"
                        self.logger.error("Ошибка неизвестна %s.", response.message)
                else:
                    self.logger.error("Пользователь %s не найден.", uid)
                    update_data["comment"] = "device not found"
                    update_data["status"] = "error"

                self.push_repo.update_message(int(item["push_id"]), update_data)
            return {"success": True, "message": "Все сообщения отправлены", "code": 200}
        finally:
            self._send_lock.release()

    # ------------------------------------------------------------------ #
    # GET /notifications/status
    # ------------------------------------------------------------------ #
    def status_messages(self) -> dict[str, Any]:
        """Refresh the status of recently-sent push messages."""
        if not self._status_lock.acquire(blocking=False):
            self.logger.error("== /notifications/status already running — skipping. ==")
            return {"success": True, "message": "already running", "code": 200}
        try:
            messages = self.push_repo.get_status_messages()
            if not messages:
                self.logger.info("---- Нет сообщений для проверки статуса ----")
                return {"success": True, "message": "Нет сообщений для проверки статуса", "code": 200}

            for item in messages:
                update_data: dict[str, Any] = {}
                mlk_id = item.get("mlk_id")
                if not mlk_id:
                    continue
                response = self.push_client.send_push(f"/notifications/{mlk_id}", method="GET")
                if response.success:
                    self.logger.info("Проверка статуса сообщения %s.", mlk_id)
                if response.success and isinstance(response.data, dict):
                    data = response.data.get("data") or {}
                    if isinstance(data, dict):
                        update_data["count_status"] = int(item.get("count_status") or 0) + 1
                        update_data["status"] = data.get("status")
                        update_data["deliver_time"] = (
                            data.get("updated_at")
                            or data.get("created_at")
                            or item.get("created_time")
                        )
                    else:
                        update_data["comment"] = f"{item.get('status')} error"
                        update_data["status"] = "error"
                else:
                    update_data["comment"] = f"{item.get('status')} error"
                    update_data["status"] = "error"
                self.push_repo.update_message(int(item["push_id"]), update_data)
            return {"success": True, "message": "Все сообщения проверены", "code": 200}
        finally:
            self._status_lock.release()

    # ------------------------------------------------------------------ #
    # GET /notifications/status-old
    # ------------------------------------------------------------------ #
    def status_messages_old(self) -> dict[str, Any]:
        """Refresh the status of long-pending push messages (retry 15..19)."""
        if not self._status_old_lock.acquire(blocking=False):
            self.logger.error("== /notifications/status-old already running — skipping. ==")
            return {"success": True, "message": "already running", "code": 200}
        try:
            messages = self.push_repo.get_status_messages_old()
            if not messages:
                self.logger.info("---- Нет сообщений old для проверки статуса ----")
                return {
                    "success": True,
                    "message": "Нет сообщений old для проверки статуса",
                    "code": 200,
                }

            for item in messages:
                update_data: dict[str, Any] = {}
                mlk_id = item.get("mlk_id")
                if not mlk_id:
                    continue
                response = self.push_client.send_push(f"/notifications/{mlk_id}", method="GET")
                if response.success:
                    self.logger.info("Проверка статуса старого сообщения %s.", mlk_id)
                if response.success and isinstance(response.data, dict):
                    data = response.data.get("data") or {}
                    if isinstance(data, dict):
                        update_data["count_status"] = int(item.get("count_status") or 0) + 1
                        update_data["status"] = data.get("status")
                        update_data["deliver_time"] = (
                            data.get("updated_at")
                            or data.get("created_at")
                            or item.get("created_time")
                        )
                        if update_data["count_status"] == 20:
                            self.logger.info(
                                "%s count_status = 20 %s deleting",
                                mlk_id, data.get("status"),
                            )
                            update_data["comment"] = f"{data.get('status')} deleting"
                            update_data["status"] = "error"
                    else:
                        update_data["comment"] = f"{item.get('status')} deleting"
                        update_data["status"] = "error"
                else:
                    self.logger.info("%s - > %s deleting", mlk_id, item.get("status"))
                    update_data["comment"] = f"{item.get('status')} deleting"
                    update_data["status"] = "error"
                self.push_repo.update_message(int(item["push_id"]), update_data)
            return {"success": True, "message": "Все сообщения old проверены", "code": 200}
        finally:
            self._status_old_lock.release()


__all__ = ["PushService"]
