"""Configuration file selection, dotted key lookup and validation."""

import pytest

from src.infrastructure.utils.config_reader import ConfigReader, ConfigurationError


def test_development_configuration_is_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("env_type", raising=False)
    monkeypatch.delenv("ENV_TYPE", raising=False)
    config = ConfigReader()
    assert config.environment == "development"
    assert "Development" in config.get("app.name")
    assert config.get_api_prefix() == "/api/v1"
    assert config.get_server_port() == 8000
    assert config.get_server_host() == "127.0.0.1"


def test_non_development_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("env_type", "production")
    config = ConfigReader()
    assert config.environment == "production"
    assert config.get("app.name") == "mT5 Persian Summarization Service"


def test_dotted_keys_and_default() -> None:
    config = ConfigReader()
    assert config.get("api.prefix") == "/api/v1"
    assert config.get("does.not.exist", "fallback") == "fallback"
    with pytest.raises(ConfigurationError, match="Missing configuration"):
        config.get("does.not.exist")
    with pytest.raises(ConfigurationError, match="Invalid configuration key"):
        config.get("bad..key")


def test_invalid_api_prefix_is_rejected() -> None:
    config = ConfigReader()
    config._settings["api"]["prefix"] = "not/a/route"
    with pytest.raises(ConfigurationError, match="api.prefix"):
        config.get_api_prefix()
