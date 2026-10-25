"""Fast delivery-contract checks; no Docker daemon or model weights required."""

from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from src.host.app import app

ROOT = Path(__file__).resolve().parents[1]


def test_docker_runtime_contract():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "python:3.12.10-slim-bookworm" in dockerfile
    assert "https://download.pytorch.org/whl/cpu" in dockerfile
    assert "--mount=type=cache,target=/root/.cache/pip" in dockerfile
    assert "pip install --timeout 180 --retries 8" in dockerfile
    assert "--no-cache-dir" not in dockerfile
    assert "PIP_NO_CACHE_DIR" not in dockerfile
    assert "USER app" in dockerfile
    assert "HF_HOME=/home/app/.cache/huggingface" in dockerfile
    assert '"--workers", "1"' in dockerfile
    assert "HEALTHCHECK" in dockerfile
    assert "src.host.app:app" in dockerfile


def test_docker_context_excludes_local_and_sensitive_files():
    patterns = set((ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines())
    assert {".git", ".venv", "tests", ".env", "*.bin", "*.safetensors"} <= patterns
    assert "!requirements.txt" in patterns


def test_compose_is_one_service_with_persistent_cache():
    config = yaml.safe_load((ROOT / "compose.yaml").read_text(encoding="utf-8"))
    assert list(config["services"]) == ["summarizer"]
    service = config["services"]["summarizer"]
    assert service["init"] is True
    assert "127.0.0.1:8000:8000" in service["ports"]
    assert "hf_cache:/home/app/.cache/huggingface" in service["volumes"]
    assert service["environment"]["env_type"] == "production"
    assert "hf_cache" in config["volumes"]


def test_health_and_openapi_are_served_without_loading_model():
    with TestClient(app) as client:
        health = client.get("/api/v1/health")
        assert health.status_code == 200
        assert health.json() == {"status": "ok"}
        assert client.get("/docs").status_code == 200
        schema = client.get("/openapi.json")
        assert schema.status_code == 200
        for route in ("text", "file", "files"):
            assert "post" in schema.json()["paths"][f"/api/v1/summarization/{route}"]


def test_model_settings_are_unchanged_between_profiles():
    base = yaml.safe_load((ROOT / "src/host/res/appsettings.yaml").read_text(encoding="utf-8"))
    dev = yaml.safe_load((ROOT / "src/host/res/appsettings.development.yaml").read_text(encoding="utf-8"))
    assert base["model"] == dev["model"]
    assert base["model"]["revision"] == "b575560ad967050e77a40f907abb1ebbeefb9a15"
    assert base["model"]["max_concurrent_inferences"] == 1
