"""Shared pytest fixtures.

The tests import the FastAPI app via :mod:`app.main` and use
:class:`httpx.Client` (sync) with the ``base_url`` parameter.  Database
access is mocked at the repository level by monkey-patching the
``BaseRepository._fetchall`` / ``_fetchone`` / ``_execute`` helpers.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def app_client() -> Iterator[TestClient]:
    """Return a :class:`TestClient` bound to the FastAPI app.

    Yields:
        A :class:`TestClient` instance.  The client is closed automatically
        at the end of the session.
    """
    # Ensure the test process uses sane defaults even without a .env file.
    os.environ.setdefault("APP_KEY", "test-app-key")
    os.environ.setdefault("JWT_KEY", "test-jwt-key")
    os.environ.setdefault("JWT_ALGORITHM", "HS256")
    os.environ.setdefault("JWT_LIFETIME", "3600")
    os.environ.setdefault("DB_HOST", "127.0.0.1")
    os.environ.setdefault("DB2_HOST", "127.0.0.1")
    os.environ.setdefault("DB3_HOST", "127.0.0.1")
    os.environ.setdefault("MAIL_URL", "http://localhost/mail")
    os.environ.setdefault("PUSH_URL", "http://localhost/push")

    # Import after env is set so Settings loads the test values.
    from app.main import create_app

    client = TestClient(create_app())
    yield client
    client.close()
