"""Фабрики движка / сессий SQLAlchemy.

Поддерживаются три независимые базы данных, зеркалирующие исходный
``App/Database.php``:

* ``db``   — основная база данных приложения (CUSTOMER, SERVICE, TARIF, FEE ...).
* ``db_client`` — webclient_logs.
* ``db_lk``     — st_logs (история ЛК).

Движки используют синхронный драйвер ``mysql+pymysql``. Пул соединений
настроен для короткоживущих сессий в рамках запроса с ``pool_pre_ping=True``,
чтобы устаревшие соединения, сброшенные сервером, незаметно обновлялись.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Final

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

#: Размер пула, используемый для каждого движка.
DEFAULT_POOL_SIZE: Final[int] = 10

#: Максимальное переполнение (дополнительные соединения сверх :data:`DEFAULT_POOL_SIZE`).
DEFAULT_MAX_OVERFLOW: Final[int] = 20

#: Время жизни соединения в секундах (поддерживает пул свежим).
DEFAULT_POOL_RECYCLE: Final[int] = 1800


def _build_engine(dsn: str) -> Engine:
    """Создать SQLAlchemy-движок для заданного DSN.

    Args:
        dsn: URL подключения ``mysql+pymysql://...``.

    Returns:
        Настроенный экземпляр :class:`sqlalchemy.engine.Engine`.
    """
    return create_engine(
        dsn,
        pool_pre_ping=True,
        pool_size=DEFAULT_POOL_SIZE,
        max_overflow=DEFAULT_MAX_OVERFLOW,
        pool_recycle=DEFAULT_POOL_RECYCLE,
        future=True,
    )


# --------------------------------------------------------------------------- #
# Движки
# --------------------------------------------------------------------------- #
engine: Engine = _build_engine(settings.db_dsn_main)
engine_client: Engine = _build_engine(settings.db_dsn_client)
engine_lk: Engine = _build_engine(settings.db_dsn_lk)


# --------------------------------------------------------------------------- #
# Фабрики сессий
# --------------------------------------------------------------------------- #
SessionLocal = sessionmaker(
    bind=engine, autoflush=False, autocommit=False, future=True, expire_on_commit=False
)
SessionLocalClient = sessionmaker(
    bind=engine_client, autoflush=False, autocommit=False, future=True, expire_on_commit=False
)
SessionLocalLk = sessionmaker(
    bind=engine_lk, autoflush=False, autocommit=False, future=True, expire_on_commit=False
)


# --------------------------------------------------------------------------- #
# Контекстные менеджеры (используются сервисами и вне цикла запроса).
# --------------------------------------------------------------------------- #
@contextmanager
def session_scope() -> Iterator[Session]:
    """Отдать сессию основной БД и автоматически сделать commit / rollback.

    Использование::

        with session_scope() as db:
            db.execute(text("SELECT 1"))

    Yields:
        SQLAlchemy :class:`~sqlalchemy.orm.Session`.
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@contextmanager
def session_scope_client() -> Iterator[Session]:
    """Отдать сессию webclient-log (подробности см. в :func:`session_scope`)."""
    session = SessionLocalClient()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@contextmanager
def session_scope_lk() -> Iterator[Session]:
    """Отдать сессию LK-log (подробности см. в :func:`session_scope`)."""
    session = SessionLocalLk()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


__all__ = [
    "engine",
    "engine_client",
    "engine_lk",
    "SessionLocal",
    "SessionLocalClient",
    "SessionLocalLk",
    "session_scope",
    "session_scope_client",
    "session_scope_lk",
]
