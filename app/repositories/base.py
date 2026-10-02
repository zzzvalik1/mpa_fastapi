"""Base repository with shared helpers."""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.exceptions import DatabaseError
from app.core.logging import get_logger


class BaseRepository:
    """Common functionality for every repository.

    Subclasses receive a SQLAlchemy :class:`~sqlalchemy.orm.Session` (one of
    the three connection pools) and use :meth:`_fetchall` / :meth:`_fetchone`
    / :meth:`_execute` to run raw SQL.  Centralising the helpers here keeps
    the SQL parameter style consistent (named parameters, ``:name``).
    """

    def __init__(self, session: Session) -> None:
        """Initialise the repository with a SQLAlchemy session.

        Args:
            session: A live :class:`Session` bound to one of the three engines.
        """
        self.session = session
        self.logger = get_logger()

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _fetchall(self, sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Run a SELECT and return all rows as dicts.

        Args:
            sql: Raw SQL statement (use ``:param`` placeholders).
            params: Optional dict of bound parameters.

        Returns:
            A list of dicts (one per row).  Returns an empty list when no
            rows are found.

        Raises:
            DatabaseError: If the underlying statement fails.
        """
        try:
            result = self.session.execute(text(sql), params or {})
            return [dict(row._mapping) for row in result.fetchall()]
        except Exception as exc:
            self.logger.exception("SQL fetchall failed: %s", exc)
            raise DatabaseError("database query failed", cause=exc) from exc

    def _fetchone(self, sql: str, params: dict[str, Any] | None = None) -> dict[str, Any] | None:
        """Run a SELECT and return a single row as a dict (or ``None``).

        Args:
            sql: Raw SQL statement.
            params: Optional dict of bound parameters.

        Returns:
            A dict representing the first row, or ``None`` if no rows match.

        Raises:
            DatabaseError: If the underlying statement fails.
        """
        try:
            result = self.session.execute(text(sql), params or {})
            row = result.fetchone()
            return dict(row._mapping) if row is not None else None
        except Exception as exc:
            self.logger.exception("SQL fetchone failed: %s", exc)
            raise DatabaseError("database query failed", cause=exc) from exc

    def _execute(self, sql: str, params: dict[str, Any] | None = None) -> int:
        """Run an INSERT / UPDATE / DELETE and return the affected row count.

        Args:
            sql: Raw SQL statement.
            params: Optional dict of bound parameters.

        Returns:
            The number of rows affected by the statement.

        Raises:
            DatabaseError: If the underlying statement fails.
        """
        try:
            result = self.session.execute(text(sql), params or {})
            return int(result.rowcount or 0)
        except Exception as exc:
            self.logger.exception("SQL execute failed: %s", exc)
            raise DatabaseError("database statement failed", cause=exc) from exc

    def _last_insert_id(self) -> int | None:
        """Return the last auto-increment id inserted on this session.

        Returns:
            The new id, or ``None`` if no INSERT has been executed yet.
        """
        try:
            row = self.session.execute(text("SELECT LAST_INSERT_ID() AS id")).fetchone()
            return int(row._mapping["id"]) if row is not None else None
        except Exception as exc:  # pragma: no cover — defensive
            self.logger.warning("Could not fetch LAST_INSERT_ID(): %s", exc)
            return None


__all__ = ["BaseRepository"]
