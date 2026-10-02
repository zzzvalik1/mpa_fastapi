"""FastAPI dependencies for database sessions.

Three dependencies are exposed — one per logical database — and each yields
a fresh :class:`~sqlalchemy.orm.Session` that is closed automatically when
the request ends.
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy.orm import Session

from app.db.session import SessionLocal, SessionLocalClient, SessionLocalLk


def get_db() -> Iterator[Session]:
    """Yield a main-DB session scoped to the request.

    Yields:
        A :class:`Session` bound to the main database.
    """
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def get_db_client() -> Iterator[Session]:
    """Yield a webclient-log session scoped to the request.

    Yields:
        A :class:`Session` bound to the webclient_logs database.
    """
    session = SessionLocalClient()
    try:
        yield session
    finally:
        session.close()


def get_db_lk() -> Iterator[Session]:
    """Yield an LK-log session scoped to the request.

    Yields:
        A :class:`Session` bound to the st_logs database.
    """
    session = SessionLocalLk()
    try:
        yield session
    finally:
        session.close()


__all__ = ["get_db", "get_db_client", "get_db_lk"]
