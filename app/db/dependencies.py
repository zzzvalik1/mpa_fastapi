"""Зависимости FastAPI для сессий базы данных.

Предоставлены три зависимости — по одной на логическую базу данных — и
каждая отдаёт свежую :class:`~sqlalchemy.orm.Session`, которая
автоматически фиксируется (commit) по завершении запроса и закрывается.

ВНИМАНИЕ: SQLAlchemy 2.x с ``autocommit=False`` (как у нас) требует
явного ``commit()`` для фиксации INSERT/UPDATE/DELETE. В PHP PDO по
умолчанию работает autocommit, поэтому каждая ``execute()`` сразу
записывается. Здесь мы эмулируем то же поведение: commit в конце запроса,
rollback при исключении.
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db.session import SessionLocal, SessionLocalClient, SessionLocalLk

_logger = get_logger()


def get_db() -> Iterator[Session]:
    """Отдать сессию основной БД, привязанную к запросу.

    Транзакция автоматически фиксируется (commit) при успешном завершении
    запроса. При возникновении исключения выполняется rollback.

    Yields:
        :class:`Session`, привязанная к основной базе данных.
    """
    session = SessionLocal()
    try:
        yield session
        # Фиксируем изменения только если запрос завершился без исключений.
        # В PHP PDO работает autocommit — каждая execute() сразу записывается;
        # здесь мы эмулируем это поведение одним commit в конце запроса.
        if session.in_transaction():
            session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db_client() -> Iterator[Session]:
    """Отдать сессию webclient-лог, привязанную к запросу.

    Транзакция автоматически фиксируется (commit) при успешном завершении
    запроса. При возникновении исключения выполняется rollback.

    Yields:
        :class:`Session`, привязанная к базе данных webclient_logs.
    """
    session = SessionLocalClient()
    try:
        yield session
        if session.in_transaction():
            session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db_lk() -> Iterator[Session]:
    """Отдать сессию LK-лог, привязанную к запросу.

    Транзакция автоматически фиксируется (commit) при успешном завершении
    запроса. При возникновении исключения выполняется rollback.

    Yields:
        :class:`Session`, привязанная к базе данных st_logs.
    """
    session = SessionLocalLk()
    try:
        yield session
        if session.in_transaction():
            session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


__all__ = ["get_db", "get_db_client", "get_db_lk"]
