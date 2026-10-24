"""Verify that Git-tracked source layers are importable after checkout."""

from importlib import import_module
from pathlib import Path


def test_core_services_namespace_package_exists() -> None:
    package = import_module("src.core.services")
    assert any(Path(location).is_dir() for location in package.__path__)
