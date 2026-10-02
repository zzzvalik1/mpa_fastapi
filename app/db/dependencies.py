"""Зависимости FastAPI для сессий базы данных.

Предоставлены три зависимости — по одной на логическую базу данных — и
каждая отдаёт свежую :class:`~sqlalchemy.orm.Session`, которая
автоматически закрывается по завершении запроса.
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy.orm import Session

from app.db.session import SessionLocal, SessionLocalClient, SessionLocalLk


def get_db() -> Iterator[Session]:
    """Отдать сессию основной БД, привязанную к запросу.

    Yields:
        :class:`Session`, привязанная к основной базе данных.
    """
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def get_db_client() -> Iterator[Session]:
    """Отдать сессию webclient-log, привязанную к запросу.

    Yields:
        :class:`Session`, привязанная к базе данных webclient_logs.
    """
    session = SessionLocalClient()
    try:
        yield session
    finally:
        session.close()


def get_db_lk() -> Iterator[Session]:
    """Отдать сессию LK-log, привязанную к запросу.

    Yields:
        :class:`Session`, привязанная к базе данных st_logs.
    """
    session = SessionLocalLk()
    try:
        yield session
    finally:
        session.close()


__all__ = ["get_db", "get_db_client", "get_db_lk"]
