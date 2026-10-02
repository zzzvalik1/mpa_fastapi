"""SQLAlchemy engine / session factories.

Three independent databases are supported, mirroring the original
``App/Database.php``:

* ``db``   — main application database (CUSTOMER, SERVICE, TARIF, FEE ...).
* ``db_client`` — webclient_logs.
* ``db_lk``     — st_logs (LK history).

The engines use a sync ``mysql+pymysql`` driver.  Connection pooling is tuned
for short-lived request-scoped sessions with ``pool_pre_ping=True`` so that
stale connections dropped by the server are silently refreshed.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Final

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

#: Pool size used for every engine.
DEFAULT_POOL_SIZE: Final[int] = 10

#: Maximum overflow (extra connections beyond :data:`DEFAULT_POOL_SIZE`).
DEFAULT_MAX_OVERFLOW: Final[int] = 20

#: Connection lifetime in seconds (keeps the pool fresh).
DEFAULT_POOL_RECYCLE: Final[int] = 1800


def _build_engine(dsn: str) -> Engine:
    """Create a SQLAlchemy engine for the given DSN.

    Args:
        dsn: ``mysql+pymysql://...`` connection URL.

    Returns:
        A configured :class:`sqlalchemy.engine.Engine` instance.
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
# Engines
# --------------------------------------------------------------------------- #
engine: Engine = _build_engine(settings.db_dsn_main)
engine_client: Engine = _build_engine(settings.db_dsn_client)
engine_lk: Engine = _build_engine(settings.db_dsn_lk)


# --------------------------------------------------------------------------- #
# Session factories
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
# Context managers (used by services outside of the request cycle too).
# --------------------------------------------------------------------------- #
@contextmanager
def session_scope() -> Iterator[Session]:
    """Yield a main-DB session and commit / rollback automatically.

    Usage::

        with session_scope() as db:
            db.execute(text("SELECT 1"))

    Yields:
        A SQLAlchemy :class:`~sqlalchemy.orm.Session`.
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
    """Yield a webclient-log session (see :func:`session_scope` for details)."""
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
    """Yield an LK-log session (see :func:`session_scope` for details)."""
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
