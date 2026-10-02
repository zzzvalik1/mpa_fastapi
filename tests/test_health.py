"""Smoke tests — verify the app boots and the health endpoint responds."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_health(app_client: TestClient) -> None:
    """``GET /health`` should return 200 and ``{"status": "ok"}``."""
    response = app_client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_openapi_available(app_client: TestClient) -> None:
    """``GET /openapi.json`` should return the OpenAPI schema."""
    response = app_client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert schema["info"]["title"] == "MPA FastAPI"


def test_unknown_route_returns_envelope(app_client: TestClient) -> None:
    """Unknown routes should return the canonical JSON envelope."""
    response = app_client.get("/api/v1/does-not-exist")
    assert response.status_code == 404
    body = response.json()
    assert body["success"] is False
    assert body["code"] == 404
