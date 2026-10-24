"""Initialize the DI registry once before application component resolution."""

from __future__ import annotations

import threading

from src.infrastructure.di.reflection import bootstrap_packages

_bootstrap_lock = threading.Lock()
_bootstrapped = False


def bootstrap_di() -> None:
    global _bootstrapped
    with _bootstrap_lock:
        if _bootstrapped:
            return
        bootstrap_packages()
        _bootstrapped = True
