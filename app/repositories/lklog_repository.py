"""Репозиторий LK-лога (порт ``App/Service/Lklog.php``).

Записывает в таблицу ``st_logs`` в **LK-базе данных** (БД №3).
"""

from __future__ import annotations

from typing import Any

from app.repositories.base import BaseRepository


class LkLogRepository(BaseRepository):
    """Репозиторий только-на-добавление для аудиторской таблицы ``st_logs``."""

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
        """Вставить одну аудиторскую строку.

        Args:
            user_id: id действующего пользователя (``None`` для анонима).
            log_info: Краткое описание действия.
            ip_addr: IP запроса.
            before_: Необязательное сериализованное состояние "до".
            after_: Необязательное сериализованное состояние "после".
            type_: Необязательная метка типа (например ``tarifChange``).

        Returns:
            Новый ``st_logs.Id`` или ``None`` при неудаче.
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
