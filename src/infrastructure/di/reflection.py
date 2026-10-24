"""Convention-based discovery of decorated components."""

from __future__ import annotations

import importlib
import inspect
from pathlib import Path

from src.infrastructure.di.inject import register_provider


_SCAN_PACKAGES = ("src.infrastructure", "src.core", "src.application")
_EXCLUDED_DIRECTORIES = frozenset(
    {"di", "dtos", "models", "scripts", "alembic", "versions", "res", "sso"}
)


class ProviderDiscoveryError(RuntimeError):
    """Raised when provider discovery cannot safely import a module."""


def bootstrap_packages() -> None:
    """Scan infrastructure, core, then application, registering only @inject classes."""
    for package_name in _SCAN_PACKAGES:
        package = importlib.import_module(package_name)
        for package_path in package.__path__:
            root = Path(package_path)
            for module_path in sorted(root.rglob("*.py")):
                relative = module_path.relative_to(root)
                if any(part in _EXCLUDED_DIRECTORIES for part in relative.parts[:-1]):
                    continue
                if module_path.name == "__init__.py":
                    continue
                module_name = ".".join((package_name, *relative.with_suffix("").parts))
                try:
                    module = importlib.import_module(module_name)
                except Exception as error:
                    raise ProviderDiscoveryError(
                        f"Failed to import DI discovery module {module_name}: {error}"
                    ) from error

                for component in vars(module).values():
                    if (
                        inspect.isclass(component)
                        and component.__module__ == module_name
                        and component.__dict__.get("__di_inject__", False)
                    ):
                        register_provider(component)
