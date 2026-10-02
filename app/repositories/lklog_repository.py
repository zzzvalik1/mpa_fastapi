"""LK-log repository (mirrors ``App/Service/Lklog.php``).

Writes to the ``st_logs`` table in the **LK database** (DB #3).
"""

from __future__ import annotations

from typing import Any

from app.repositories.base import BaseRepository


class LkLogRepository(BaseRepository):
    """Append-only writer for the ``st_logs`` audit table."""

    def insert_lklog(
        self,
        *,
        user_id: int | None,
        log_info: str,
        ip_addr: str,
        before_: str | None = None,
        after_: str | None = None,
        type_: str | None = None,
    ) -> int | None:
        """Insert a single audit row.

        Args:
            user_id: Acting user id (``None`` for anonymous).
            log_info: Short description of the action.
            ip_addr: Request IP.
            before_: Optional serialised "before" state.
            after_: Optional serialised "after" state.
            type_: Optional type tag (e.g. ``tarifChange``).

        Returns:
            The new ``st_logs.Id``, or ``None`` on failure.
        """
        sql = """
            INSERT INTO `st_logs`
                (`DateTime`, `UserId`, `LogInfo`, `IpAddr`, `Before`, `After`, `Type`)
            VALUES
                (NOW(), :user_id, :log_info, :ip_addr, :before, :after, :type)
        """
        self._execute(
            sql,
            {
                "user_id": user_id,
                "log_info": log_info,
                "ip_addr": ip_addr,
                "before": before_,
                "after": after_,
                "type": type_,
            },
        )
        return self._last_insert_id()


__all__ = ["LkLogRepository"]
