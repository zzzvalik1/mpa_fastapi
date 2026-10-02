"""Базовый репозиторий с общими хелперами."""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.exceptions import DatabaseError
from app.core.logging import get_logger


class BaseRepository:
    """Общая функциональность для всех репозиториев.

    Подклассы получают :class:`~sqlalchemy.orm.Session` SQLAlchemy (одну из
    трёх пулов соединений) и используют :meth:`_fetchall` / :meth:`_fetchone`
    / :meth:`_execute` для выполнения сырого SQL.  Централизация хелперов
    здесь сохраняет единый стиль параметров SQL (именованные параметры,
    ``:name``).
    """

    def __init__(self, session: Session) -> None:
        """Инициализировать репозиторий сессией SQLAlchemy.

        Args:
            session: Активная :class:`Session`, привязанная к одному из трёх движков.
        """
        self.session = session
        self.logger = get_logger()

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _fetchall(self, sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Выполнить SELECT и вернуть все строки как словари.

        Args:
            sql: Сырая SQL-инструкция (используйте плейсхолдеры ``:param``).
            params: Необязательный словарь связанных параметров.

        Returns:
            Список словарей (по одному на строку).  Возвращает пустой список,
            если строки не найдены.

        Raises:
            DatabaseError: Если выполнение инструкции завершилось ошибкой.
        """
        try:
            result = self.session.execute(text(sql), params or {})
            return [dict(row._mapping) for row in result.fetchall()]
        except Exception as exc:
            self.logger.exception("SQL fetchall failed: %s", exc)
            raise DatabaseError("database query failed", cause=exc) from exc

    def _fetchone(self, sql: str, params: dict[str, Any] | None = None) -> dict[str, Any] | None:
        """Выполнить SELECT и вернуть одну строку как словарь (или ``None``).

        Args:
            sql: Сырая SQL-инструкция.
            params: Необязательный словарь связанных параметров.

        Returns:
            Словарь, представляющий первую строку, или ``None``, если строки
            не найдены.

        Raises:
            DatabaseError: Если выполнение инструкции завершилось ошибкой.
        """
        try:
            result = self.session.execute(text(sql), params or {})
            row = result.fetchone()
            return dict(row._mapping) if row is not None else None
        except Exception as exc:
            self.logger.exception("SQL fetchone failed: %s", exc)
            raise DatabaseError("database query failed", cause=exc) from exc

    def _execute(self, sql: str, params: dict[str, Any] | None = None) -> int:
        """Выполнить INSERT / UPDATE / DELETE и вернуть количество затронутых строк.

        Args:
            sql: Сырая SQL-инструкция.
            params: Необязательный словарь связанных параметров.

        Returns:
            Количество строк, затронутых инструкцией.

        Raises:
            DatabaseError: Если выполнение инструкции завершилось ошибкой.
        """
        try:
            result = self.session.execute(text(sql), params or {})
            return int(result.rowcount or 0)
        except Exception as exc:
            self.logger.exception("SQL execute failed: %s", exc)
            raise DatabaseError("database statement failed", cause=exc) from exc

    def _last_insert_id(self) -> int | None:
        """Вернуть последний auto-increment ID, вставленный в этой сессии.

        Returns:
            Новый id или ``None``, если INSERT ещё не выполнялся.
        """
        try:
            row = self.session.execute(text("SELECT LAST_INSERT_ID() AS id")).fetchone()
            return int(row._mapping["id"]) if row is not None else None
        except Exception as exc:  # pragma: no cover — defensive
            self.logger.warning("Could not fetch LAST_INSERT_ID(): %s", exc)
            return None


__all__ = ["BaseRepository"]
