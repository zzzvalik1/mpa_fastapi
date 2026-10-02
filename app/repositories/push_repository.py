"""Репозиторий push (порт ``App/Service/Push.php``).

Поток push записывает в ``PUSH_MESSAGES_MLK`` в *основной* базе данных.
"""

from __future__ import annotations

from typing import Any

from app.repositories.base import BaseRepository


class PushRepository(BaseRepository):
    """Чтение/запись таблицы ``PUSH_MESSAGES_MLK``."""

    def get_wait_messages(self) -> list[dict[str, Any]]:
        """Вернуть все сообщения, ожидающие отправки (status = 'sended')."""
        sql = """
            SELECT *
            FROM `PUSH_MESSAGES_MLK`
            WHERE `status` = 'sended'
            ORDER BY `created_time` ASC
        """
        return self._fetchall(sql)

    def get_status_messages(self) -> list[dict[str, Any]]:
        """Вернуть сообщения, статус которых ещё в ожидании (максимум 15 попыток)."""
        sql = """
            SELECT `push_id`, `mlk_id`, `status`, `count_status`, `created_time`
            FROM `PUSH_MESSAGES_MLK`
            WHERE `status` IN ('pending', 'delivered')
              AND `mlk_id` IS NOT NULL
              AND DATEDIFF(NOW(), `created_time`) < 6
              AND `count_status` < 15
            ORDER BY `created_time` ASC
        """
        return self._fetchall(sql)

    def get_status_messages_old(self) -> list[dict[str, Any]]:
        """Вернуть старые сообщения, ещё в ожидании (количество попыток 15..19)."""
        sql = """
            SELECT `push_id`, `mlk_id`, `status`, `count_status`, `created_time`
            FROM `PUSH_MESSAGES_MLK`
            WHERE `status` IN ('pending', 'delivered')
              AND `mlk_id` IS NOT NULL
              AND `count_status` >= 15
              AND `count_status` < 20
              AND `comment` IS NULL
            ORDER BY `created_time` ASC
        """
        return self._fetchall(sql)

    def update_message(self, push_id: int, update_data: dict[str, Any]) -> bool:
        """Обновить один или несколько столбцов в ``PUSH_MESSAGES_MLK`` по ``push_id``."""
        if not update_data:
            return False
        set_clause = ", ".join(f"`{c}` = :{c}" for c in update_data)
        params = dict(update_data)
        params["push_id"] = push_id
        sql = f"UPDATE `PUSH_MESSAGES_MLK` SET {set_clause} WHERE `push_id` = :push_id"
        return self._execute(sql, params) >= 0


__all__ = ["PushRepository"]
