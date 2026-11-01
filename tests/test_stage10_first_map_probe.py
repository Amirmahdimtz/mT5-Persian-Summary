"""Offline single-map probe tests; no real model download or source copies."""

from __future__ import annotations

import asyncio
import json
import sys
from types import ModuleType

import pytest

from benchmarks.quality_benchmark import BenchmarkInputError, DATASET, read_json
from benchmarks.stage10_first_map_probe import execute_async, main
from benchmarks.stage10_trace import select_dev_case


def test_probe_requires_explicit_local_generated_text_acknowledgement():
    with pytest.raises(SystemExit) as exc:
        main(["--dataset", str(DATASET), "--case-id", "weather_short", "--output", "local_stage10_probe.json"])
    assert exc.value.code == 2


def test_probe_rejects_holdout_and_missing_source():
    data = read_json(DATASET)
    with pytest.raises(BenchmarkInputError, match="holdout"):
        select_dev_case(data, "meeting_holdout")
    with pytest.raises(BenchmarkInputError, match="not found"):
        select_dev_case(data, "missing")


def test_probe_runs_one_map_call_and_no_original_input_saved(monkeypatch, tmp_path):
    provider_module = ModuleType("src.infrastructure.ml.mt5_model_provider")
    service_module = ModuleType("src.core.services.summarization.long_text_summarization_service")
    injector = ModuleType("src.infrastructure.di.inject")
    bootstrap = ModuleType("src.infrastructure.di.bootstrap")
    configs = ModuleType("src.infrastructure.utils.config_reader")

    data = read_json(DATASET)
    short_case = next(x for x in data["cases"] if x["id"] == "weather_short")
    assert short_case["split"] == "dev"

    class FakeChunker:
        def normalize(self, text):
            return text.strip()

        def chunk(self, text):
            midpoint = text.index(" ", max(1, len(text) // 2))
            return [text[:midpoint + 1], text[midpoint + 1:]]

    class FakeProvider:
        max_output_tokens = 120

        def __init__(self):
            self.calls = []

        async def summarize_async(self, text, *, max_output_tokens=None):
            self.calls.append((text, max_output_tokens))
            return "خلاصه برای بررسی بازبین"

        def count_input_tokens(self, text):
            return len(text.split()) + 1

    provider = FakeProvider()

    class FakeService:
        _provider = provider
        _chunker = FakeChunker()

    provider_module.Mt5ModelProvider = FakeProvider
    service_module.LongTextSummarizationService = FakeService
    injector.resolve = lambda typ: provider if typ is FakeProvider else FakeService()
    bootstrap.bootstrap_di = lambda: None

    class FakeConfig:
        def get(self, key):
            assert key == "model"
            return {"revision": "a" * 40, "no_repeat_ngram_size": 3}

    configs.ConfigReader = FakeConfig
    for name, module in (
        ("src.infrastructure.ml.mt5_model_provider", provider_module),
        ("src.core.services.summarization.long_text_summarization_service", service_module),
        ("src.infrastructure.di.inject", injector),
        ("src.infrastructure.di.bootstrap", bootstrap),
        ("src.infrastructure.utils.config_reader", configs),
    ):
        monkeypatch.setitem(sys.modules, name, module)

    path = tmp_path / "local_stage10_probe.json"
    asyncio.run(execute_async(DATASET, "weather_short", path))
    result = read_json(path)
    assert result["stage"] == "first_map_only"
    assert result["first_map_generated_text"] == "خلاصه برای بررسی بازبین"
    assert len(provider.calls) == 1
    assert provider.calls[0][1] == 120
    assert "سازمان هواشناسی" not in json.dumps(result, ensure_ascii=False)
    assert result["no_repeat_ngram_size"] == 3
    assert result["chunk_count"] == 2
    with pytest.raises(BenchmarkInputError, match="already exists"):
        asyncio.run(execute_async(DATASET, "weather_short", path))
    assert len(provider.calls) == 1


def test_no_second_model_call_when_chunking_says_one_chunk(monkeypatch, tmp_path):
    # Verify the single-chunk source is not mislabelled as the first map stage.
    from benchmarks.stage10_first_map_probe import execute_async
    mod = ModuleType("src.core.services.summarization.long_text_summarization_service")
    class FakeChunker:
        def normalize(self, value): return value.strip()
        def chunk(self, value): return [value]
    class FakeProvider:
        max_output_tokens = 120
    provider = FakeProvider()
    class FakeService:
        _provider = provider
        _chunker = FakeChunker()
    mod.LongTextSummarizationService = FakeService
    pmod = ModuleType("src.infrastructure.ml.mt5_model_provider")
    pmod.Mt5ModelProvider = FakeProvider
    di = ModuleType("src.infrastructure.di.inject")
    di.resolve = lambda typ: provider if typ is FakeProvider else FakeService()
    boot = ModuleType("src.infrastructure.di.bootstrap")
    boot.bootstrap_di = lambda: None
    configs = ModuleType("src.infrastructure.utils.config_reader")
    configs.ConfigReader = type("FakeConfig", (), {})
    for name, v in (
        ("src.core.services.summarization.long_text_summarization_service", mod),
        ("src.infrastructure.ml.mt5_model_provider", pmod),
        ("src.infrastructure.di.inject", di),
        ("src.infrastructure.di.bootstrap", boot),
        ("src.infrastructure.utils.config_reader", configs),
    ):
        monkeypatch.setitem(sys.modules, name, v)
    with pytest.raises(BenchmarkInputError, match="does not need"):
        asyncio.run(execute_async(DATASET, "weather_short", tmp_path / "none.json"))
