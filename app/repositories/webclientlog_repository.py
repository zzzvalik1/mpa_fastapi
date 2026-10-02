"""Web-client-log repository (mirrors ``App/Service/Webclientlog.php``).

Writes to the ``webclient_logs`` table in the **webclient database** (DB #2).
"""

from __future__ import annotations

from app.repositories.base import BaseRepository


class WebClientLogRepository(BaseRepository):
    """Append-only writer for the ``webclient_logs`` audit table."""

    def insert_webclientlog(
        self,
        *,
        user_id: int | None,
        client_id: int = 1,
        log_info: str,
        ip_addr: str,
        before_: str | None = None,
        after_: str | None = None,
        type_: str | None = None,
    ) -> int | None:
        """Insert a single audit row.

        Args:
            user_id: Acting user id.
            client_id: Client id (default 1 — MLK).
            log_info: Short description of the action.
            ip_addr: Request IP.
            before_: Optional serialised "before" state.
            after_: Optional serialised "after" state.
            type_: Optional type tag.

        Returns:
            The new ``webclient_logs.Id``, or ``None`` on failure.
        """
        sql = """
            INSERT INTO `webclient_logs`
                (`DateTime`, `UserId`, `ClientId`, `LogInfo`, `IpAddr`, `Before`, `After`, `Type`)
            VALUES
                (NOW(), :user_id, :client_id, :log_info, :ip_addr, :before, :after, :type)
        """
        self._execute(
            sql,
            {
                "user_id": user_id,
                "client_id": client_id,
                "log_info": log_info,
                "ip_addr": ip_addr,
                "before": before_,
                "after": after_,
                "type": type_,
            },
        )
        return self._last_insert_id()


__all__ = ["WebClientLogRepository"]
