"""Environment-aware YAML configuration reader."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml

from src.infrastructure.di.inject import inject


class ConfigurationError(ValueError):
    """Raised for absent, invalid, or incorrectly typed configuration."""


_MISSING = object()
_SETTINGS_DIR = Path(__file__).resolve().parents[2] / "host" / "res"
_PREFIX_PATTERN = re.compile(r"/[a-zA-Z0-9_-]+(?:/[a-zA-Z0-9_-]+)*")


@inject
class ConfigReader:
    __di_singleton__ = True

    def __init__(self) -> None:
        self.environment = (
            os.environ.get("env_type") or os.environ.get("ENV_TYPE") or "development"
        ).lower()
        filename = (
            "appsettings.development.yaml"
            if self.environment == "development"
            else "appsettings.yaml"
        )
        settings_path = _SETTINGS_DIR / filename
        try:
            with settings_path.open("r", encoding="utf-8") as handle:
                loaded = yaml.safe_load(handle)
        except (OSError, yaml.YAMLError) as error:
            raise ConfigurationError(
                f"Cannot load configuration from {settings_path}: {error}"
            ) from error
        if not isinstance(loaded, dict):
            raise ConfigurationError(f"Configuration must be a YAML mapping: {settings_path}")
        self._settings: dict[str, Any] = loaded

    def get(self, key: str, default: Any = _MISSING) -> Any:
        if not key or not all(key.split(".")):
            raise ConfigurationError(f"Invalid configuration key: {key!r}")
        value: Any = self._settings
        for part in key.split("."):
            if not isinstance(value, dict) or part not in value:
                if default is not _MISSING:
                    return default
                raise ConfigurationError(f"Missing configuration value: {key}")
            value = value[part]
        return value

    def get_api_prefix(self) -> str:
        prefix = self.get("api.prefix")
        if not isinstance(prefix, str) or not _PREFIX_PATTERN.fullmatch(prefix):
            raise ConfigurationError("api.prefix must be a path such as '/api/v1'")
        return prefix

    def get_server_port(self) -> int:
        port = self.get("server.port")
        if type(port) is not int or not 1 <= port <= 65535:
            raise ConfigurationError("server.port must be an integer between 1 and 65535")
        return port

    def get_server_host(self) -> str:
        host = self.get("server.host")
        if not isinstance(host, str) or not host.strip():
            raise ConfigurationError("server.host must be a non-empty string")
        return host
