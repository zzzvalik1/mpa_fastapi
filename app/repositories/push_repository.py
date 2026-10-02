"""Push repository (mirrors ``App/Service/Push.php``).

The push workflow writes to ``PUSH_MESSAGES_MLK`` in the *main* database.
"""

from __future__ import annotations

from typing import Any

from app.repositories.base import BaseRepository


class PushRepository(BaseRepository):
    """Read / write access to the ``PUSH_MESSAGES_MLK`` table."""

    def get_wait_messages(self) -> list[dict[str, Any]]:
        """Return all messages waiting to be sent (status = 'sended')."""
        sql = """
            SELECT *
            FROM `PUSH_MESSAGES_MLK`
            WHERE `status` = 'sended'
            ORDER BY `created_time` ASC
        """
        return self._fetchall(sql)

    def get_status_messages(self) -> list[dict[str, Any]]:
        """Return messages whose status is still pending (max 15 retries)."""
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
        """Return old messages still pending (retry count 15..19)."""
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
        """Update one or more columns on ``PUSH_MESSAGES_MLK`` by ``push_id``."""
        if not update_data:
            return False
        set_clause = ", ".join(f"`{c}` = :{c}" for c in update_data)
        params = dict(update_data)
        params["push_id"] = push_id
        sql = f"UPDATE `PUSH_MESSAGES_MLK` SET {set_clause} WHERE `push_id` = :push_id"
        return self._execute(sql, params) >= 0


__all__ = ["PushRepository"]
