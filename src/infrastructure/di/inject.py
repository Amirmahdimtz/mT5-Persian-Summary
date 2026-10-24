"""Minimal convention-based constructor DI for application components."""

from __future__ import annotations

import inspect
import threading
from functools import wraps
from typing import TypeVar, get_type_hints


T = TypeVar("T")
_providers: dict[type, type] = {}
_singletons: dict[type, object] = {}
_lock = threading.RLock()
_resolution_state = threading.local()


class DependencyResolutionError(RuntimeError):
    """Raised when a constructor dependency cannot be resolved."""


def register_provider(provider: type) -> None:
    """Register a discovered @inject class by its concrete type and eligible bases."""
    if not provider.__dict__.get("__di_inject__", False):
        return

    with _lock:
        interfaces = [
            base
            for base in inspect.getmro(provider)[1:]
            if base is not object
            and base.__module__ != "abc"
            and (
                base.__name__.startswith("I")
                or bool(getattr(base, "__abstractmethods__", False))
            )
        ]
        for service_type in (provider, *interfaces):
            previous = _providers.get(service_type)
            if previous is not None and previous is not provider:
                raise DependencyResolutionError(
                    f"Ambiguous DI provider for {service_type.__module__}."
                    f"{service_type.__qualname__}: {previous.__qualname__} and "
                    f"{provider.__qualname__}"
                )
            _providers[service_type] = provider


def resolve(service_type: type[T]) -> T:
    """Resolve a previously discovered dependency, caching marked singletons."""
    with _lock:
        provider = _providers.get(service_type)
        if provider is None:
            raise DependencyResolutionError(
                f"No registered DI provider for {service_type!r}. "
                "Call bootstrap_di() before resolving dependencies."
            )

        if provider.__dict__.get("__di_singleton__", False):
            cached = _singletons.get(provider)
            if cached is not None:
                return cached  # type: ignore[return-value]

        stack: list[type] = getattr(_resolution_state, "stack", [])
        if provider in stack:
            chain = " -> ".join(cls.__qualname__ for cls in (*stack, provider))
            raise DependencyResolutionError(f"Circular DI dependency: {chain}")

        _resolution_state.stack = [*stack, provider]
        try:
            instance = provider()
            if provider.__dict__.get("__di_singleton__", False):
                _singletons[provider] = instance
            return instance
        finally:
            _resolution_state.stack = stack


def inject(cls: type[T]) -> type[T]:
    """Inject missing, required constructor parameters using their type hints."""
    if cls.__dict__.get("__di_inject__", False):
        return cls

    original_init = cls.__init__
    signature = inspect.signature(original_init)

    @wraps(original_init)
    def wrapped_init(self: object, *args: object, **kwargs: object) -> None:
        bound = signature.bind_partial(self, *args, **kwargs)
        required = [
            (name, parameter)
            for name, parameter in signature.parameters.items()
            if name != "self"
            and name not in bound.arguments
            and parameter.default is inspect.Parameter.empty
            and parameter.kind
            not in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
        ]
        if required:
            try:
                hints = get_type_hints(original_init)
            except (NameError, TypeError) as error:
                raise DependencyResolutionError(
                    f"Unable to evaluate constructor annotations for "
                    f"{cls.__module__}.{cls.__qualname__}: {error}"
                ) from error
            for name, _ in required:
                dependency_type = hints.get(name)
                if not isinstance(dependency_type, type):
                    raise DependencyResolutionError(
                        f"Missing concrete type annotation for "
                        f"{cls.__qualname__}.{name}"
                    )
                bound.arguments[name] = resolve(dependency_type)

        original_init(*bound.args, **bound.kwargs)

    cls.__init__ = wrapped_init  # type: ignore[method-assign]
    cls.__di_inject__ = True  # type: ignore[attr-defined]
    return cls
