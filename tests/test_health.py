"""Smoke-тесты — проверка что приложение запускается и health-эндпоинт отвечает."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_health(app_client: TestClient) -> None:
    """``GET /health`` должен вернуть 200 и ``{"status": "ok"}``."""
    response = app_client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_openapi_available(app_client: TestClient) -> None:
    """``GET /openapi.json`` должен вернуть OpenAPI-схему."""
    response = app_client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert schema["info"]["title"] == "MPA FastAPI"


def test_unknown_route_returns_envelope(app_client: TestClient) -> None:
    """Неизвестные маршруты должны возвращать канонический JSON-конверт."""
    response = app_client.get("/api/v1/does-not-exist")
    assert response.status_code == 404
    body = response.json()
    assert body["success"] is False
    assert body["code"] == 404
