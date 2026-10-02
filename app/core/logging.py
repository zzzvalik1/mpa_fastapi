"""Logging configuration.

Two named loggers are configured:

* ``logged`` — the main application logger used by controllers / services.
* ``push_log`` — a separate logger for the push-notification worker endpoints.

Both loggers write to **time-rotated** files kept for
:data:`Settings.log_retention_days` days (30 by default).  A separate file is
created per calendar day, so the on-disk layout looks like:

::

    storage/logs/log.log          ← today
    storage/logs/log.log.2025-10-01
    storage/logs/log.log.2025-09-30
    ...

A ``logging.StreamHandler`` is also attached so logs are mirrored to stdout
(this is the convention inside Docker containers).
"""

from __future__ import annotations

import logging
import os
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Final

from app.core.config import Settings, settings as _settings

#: Name of the main application logger.
LOGGER_NAME: Final[str] = "logged"

#: Name of the push-notification logger.
PUSH_LOGGER_NAME: Final[str] = "push_log"

#: Format used for both file and console output.
_LOG_FORMAT: Final[str] = (
    "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
)
_LOG_DATE_FORMAT: Final[str] = "%Y-%m-%d %H:%M:%S"


def _ensure_log_dir(log_dir: str) -> Path:
    """Create the log directory if it does not already exist.

    Args:
        log_dir: Relative or absolute path to the log directory.

    Returns:
        The :class:`pathlib.Path` for the (now-existing) directory.
    """
    path = Path(log_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _build_logger(
    name: str,
    log_file_name: str,
    settings: Settings,
) -> logging.Logger:
    """Build and configure a single named logger.

    Args:
        name: Logger name (exposed to callers via :func:`logging.getLogger`).
        log_file_name: Base file name (``log`` or ``push_log``).
        settings: Application settings used for path / level / retention.

    Returns:
        A configured :class:`logging.Logger` instance.
    """
    logger = logging.getLogger(name)
    logger.setLevel(settings.log_level_int)
    # Avoid double-attaching handlers if called twice (e.g. during tests).
    if logger.handlers:
        return logger

    log_dir = _ensure_log_dir(settings.log_dir)
    log_path = log_dir / f"{log_file_name}.log"

    file_handler = TimedRotatingFileHandler(
        filename=str(log_path),
        when="midnight",
        interval=1,
        backupCount=settings.log_retention_days,
        encoding="utf-8",
        utc=False,
    )
    file_handler.suffix = "%Y-%m-%d"  # noqa: E501 — used by TimedRotatingFileHandler
    file_handler.setFormatter(logging.Formatter(_LOG_FORMAT, _LOG_DATE_FORMAT))

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(logging.Formatter(_LOG_FORMAT, _LOG_DATE_FORMAT))

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    logger.propagate = False
    return logger


def setup_logging(settings: Settings = _settings) -> logging.Logger:
    """Initialise both named loggers and return the main one.

    This function is idempotent — it is safe to call multiple times.

    Args:
        settings: Application settings (defaults to the global singleton).

    Returns:
        The main application logger.
    """
    main_logger = _build_logger(LOGGER_NAME, "log", settings)
    _build_logger(PUSH_LOGGER_NAME, "push_log", settings)
    # Ensure the root logger does not swallow our messages.
    logging.getLogger().setLevel(logging.WARNING)
    return main_logger


def get_logger(name: str = LOGGER_NAME) -> logging.Logger:
    """Return a logger configured by :func:`setup_logging`.

    Args:
        name: Optional logger name (defaults to the main application logger).

    Returns:
        A :class:`logging.Logger` instance.
    """
    return logging.getLogger(name)


def get_push_logger() -> logging.Logger:
    """Return the push-notification logger.

    Returns:
        A :class:`logging.Logger` instance for push-related events.
    """
    return logging.getLogger(PUSH_LOGGER_NAME)


__all__ = [
    "LOGGER_NAME",
    "PUSH_LOGGER_NAME",
    "setup_logging",
    "get_logger",
    "get_push_logger",
]
