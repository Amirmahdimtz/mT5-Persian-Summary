"""DI bootstrap, injection semantics and lifecycle."""

import pytest

from src.application.web import WebService
from src.infrastructure.di.bootstrap import bootstrap_di
from src.infrastructure.di.inject import DependencyResolutionError, inject, resolve
from src.infrastructure.utils.config_reader import ConfigReader


def test_bootstrap_is_idempotent() -> None:
    bootstrap_di()
    bootstrap_di()
    assert isinstance(resolve(WebService), WebService)


def test_singleton_config_reader() -> None:
    bootstrap_di()
    assert resolve(ConfigReader) is resolve(ConfigReader)


def test_constructor_injection_resolves_dependency() -> None:
    bootstrap_di()

    @inject
    class Consumer:
        def __init__(self, config: ConfigReader) -> None:
            self.config = config

    consumer = Consumer()
    assert consumer.config is resolve(ConfigReader)


def test_explicit_argument_is_not_overwritten() -> None:
    bootstrap_di()

    @inject
    class Consumer:
        def __init__(self, config: ConfigReader) -> None:
            self.config = config

    explicitly_supplied = ConfigReader()
    assert Consumer(explicitly_supplied).config is explicitly_supplied


def test_default_argument_is_not_injected() -> None:
    bootstrap_di()

    @inject
    class Consumer:
        def __init__(self, config: ConfigReader | None = None) -> None:
            self.config = config

    assert Consumer().config is None


def test_unknown_dependency_has_actionable_error() -> None:
    bootstrap_di()

    class Unknown:
        pass

    with pytest.raises(DependencyResolutionError, match="No registered DI provider"):
        resolve(Unknown)


def test_missing_annotation_is_reported() -> None:
    @inject
    class Consumer:
        def __init__(self, dependency) -> None:
            self.dependency = dependency

    with pytest.raises(DependencyResolutionError, match="Missing concrete type annotation"):
        Consumer()
