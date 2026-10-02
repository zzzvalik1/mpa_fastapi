"""Общие pytest-фикстуры.

Тесты импортируют FastAPI-приложение через :mod:`app.main` и используют
:class:`httpx.Client` (синхронный) с параметром ``base_url``.  Доступ к БД
мокируется на уровне репозиториев путём monkey-patching хелперов
``BaseRepository._fetchall`` / ``_fetchone`` / ``_execute``.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def app_client() -> Iterator[TestClient]:
    """Вернуть :class:`TestClient`, привязанный к FastAPI-приложению.

    Yields:
        Экземпляр :class:`TestClient`.  Клиент автоматически закрывается
        в конце сессии.
    """
    # Гарантируем, что тестовый процесс использует разумные значения по умолчанию даже без .env.
    os.environ.setdefault("APP_KEY", "test-app-key")
    os.environ.setdefault("JWT_KEY", "test-jwt-key")
    os.environ.setdefault("JWT_ALGORITHM", "HS256")
    os.environ.setdefault("JWT_LIFETIME", "3600")
    os.environ.setdefault("DB_HOST", "127.0.0.1")
    os.environ.setdefault("DB2_HOST", "127.0.0.1")
    os.environ.setdefault("DB3_HOST", "127.0.0.1")
    os.environ.setdefault("MAIL_URL", "http://localhost/mail")
    os.environ.setdefault("PUSH_URL", "http://localhost/push")

    # Импорт после установки переменных окружения, чтобы Settings загрузила тестовые значения.
    from app.main import create_app

    client = TestClient(create_app())
    yield client
    client.close()
