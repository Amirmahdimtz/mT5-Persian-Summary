"""ASGI initialization, controller discovery and HTTP smoke checks."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.host.app import app, create_app
from src.infrastructure.di.inject import resolve
from src.infrastructure.utils.config_reader import ConfigReader


def test_app_initializes_with_configured_metadata() -> None:
    initialized = create_app()
    assert isinstance(initialized, FastAPI)
    assert initialized.title == resolve(ConfigReader).get("app.name")
    assert initialized.version == "0.1.0"


def test_auto_discovered_health_route() -> None:
    assert any(route.path == "/api/v1/health" for route in app.routes)


def test_health_check_http_response() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_openapi_lists_health_endpoint() -> None:
    with TestClient(app) as client:
        response = client.get("/openapi.json")
        swagger = client.get("/docs")
    assert response.status_code == 200
    assert swagger.status_code == 200
    assert "/api/v1/health" in response.json()["paths"]
    assert "get" in response.json()["paths"]["/api/v1/health"]
