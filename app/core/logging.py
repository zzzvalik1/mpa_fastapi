"""Конфигурация логирования.

Настраиваются два именованных логгера:

* ``logged`` — основной логгер приложения, используемый контроллерами / сервисами.
* ``push_log`` — отдельный логгер для эндпоинтов воркера push-уведомлений.

Оба логгера пишут в **ротируемые по времени** файлы, которые хранятся
:data:`Settings.log_retention_days` дней (по умолчанию 30). На каждый
календарный день создаётся отдельный файл, поэтому расположение на диске
выглядит так:

::

    storage/logs/log.log          ← сегодня
    storage/logs/log.log.2025-10-01
    storage/logs/log.log.2025-09-30
    ...

Также подключается ``logging.StreamHandler``, чтобы логи дублировались
в stdout (это соглашение внутри Docker-контейнеров).
"""

from __future__ import annotations

import logging
import os
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Final

from app.core.config import Settings, settings as _settings

#: Имя основного логгера приложения.
LOGGER_NAME: Final[str] = "logged"

#: Имя логгера push-уведомлений.
PUSH_LOGGER_NAME: Final[str] = "push_log"

#: Формат, используемый и для файлового, и для консольного вывода.
_LOG_FORMAT: Final[str] = (
    "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
)
_LOG_DATE_FORMAT: Final[str] = "%Y-%m-%d %H:%M:%S"


def _ensure_log_dir(log_dir: str) -> Path:
    """Создать директорию логов, если она ещё не существует.

    Args:
        log_dir: Относительный или абсолютный путь к директории логов.

    Returns:
        :class:`pathlib.Path` для (теперь существующей) директории.
    """
    path = Path(log_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _build_logger(
    name: str,
    log_file_name: str,
    settings: Settings,
) -> logging.Logger:
    """Собрать и настроить один именованный логгер.

    Args:
        name: Имя логгера (доступно вызовающим через :func:`logging.getLogger`).
        log_file_name: Базовое имя файла (``log`` или ``push_log``).
        settings: Настройки приложения, используемые для пути / уровня / срока хранения.

    Returns:
        Настроенный экземпляр :class:`logging.Logger`.
    """
    logger = logging.getLogger(name)
    logger.setLevel(settings.log_level_int)
    # Не подключать обработчики дважды при повторном вызове (например, в тестах).
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
    """Инициализировать оба именованных логгера и вернуть основной.

    Эта функция идемпотентна — её безопасно вызывать многократно.

    Args:
        settings: Настройки приложения (по умолчанию глобальный синглтон).

    Returns:
        Основной логгер приложения.
    """
    main_logger = _build_logger(LOGGER_NAME, "log", settings)
    _build_logger(PUSH_LOGGER_NAME, "push_log", settings)
    # Убедиться, что корневой логгер не поглощает наши сообщения.
    logging.getLogger().setLevel(logging.WARNING)
    return main_logger


def get_logger(name: str = LOGGER_NAME) -> logging.Logger:
    """Вернуть логгер, настроенный функцией :func:`setup_logging`.

    Args:
        name: Необязательное имя логгера (по умолчанию основной логгер приложения).

    Returns:
        Экземпляр :class:`logging.Logger`.
    """
    return logging.getLogger(name)


def get_push_logger() -> logging.Logger:
    """Вернуть логгер push-уведомлений.

    Returns:
        Экземпляр :class:`logging.Logger` для событий, связанных с push.
    """
    return logging.getLogger(PUSH_LOGGER_NAME)


__all__ = [
    "LOGGER_NAME",
    "PUSH_LOGGER_NAME",
    "setup_logging",
    "get_logger",
    "get_push_logger",
]
