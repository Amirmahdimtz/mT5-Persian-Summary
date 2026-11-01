"""Offline Stage 10 trace tests, without model weights or network."""

from __future__ import annotations

import asyncio

import pytest

from benchmarks.quality_benchmark import BenchmarkInputError, DATASET, read_json
from benchmarks.stage10_trace import CallRecorder, select_dev_case


def run(coro):
    return asyncio.run(coro)


def test_record_source_and_generated_literal_fact_survival_without_raw_content():
    text = "بودجه پروژه ۳۵۰ میلیون تومان تعیین شد."
    facts = [{"id": "budget", "source_quote": "۳۵۰ میلیون تومان"}]
    recorder = CallRecorder(text, facts)

    async def infer(value, *, max_output_tokens=None):
        assert value == text
        assert max_output_tokens == 80
        return "بودجه ۳۵۰ میلیون تومان ثبت شد"

    wrapped = recorder.wrap(infer)
    assert "۳۵۰ میلیون تومان" in run(wrapped(text, max_output_tokens=80))
    assert recorder.calls[0]["input_is_original_source_span"] is True
    assert recorder.calls[0]["input_contains_exact_fact_quotes"] == ["budget"]
    assert recorder.calls[0]["output_contains_exact_fact_quotes"] == ["budget"]
    assert "بودجه" not in str(recorder.calls)  # No raw input/output content persisted.


def test_intermediate_reduction_and_error_are_recorded_without_leak():
    rec = CallRecorder("متن اصلی", [{"id": "fact", "source_quote": "متن اصلی"}])

    async def failing(text, *, max_output_tokens=None):
        raise RuntimeError("private document text")

    with pytest.raises(RuntimeError, match="private document text"):
        run(rec.wrap(failing)("خلاصه میانی", max_output_tokens=40))
    entry = rec.calls[0]
    assert entry["input_is_original_source_span"] is False
    assert entry["error_code"] == "RuntimeError"
    assert "private document text" not in str(entry)
    assert "خلاصه میانی" not in str(entry)


def test_holdout_is_rejected_and_dev_selection_works():
    data = read_json(DATASET)
    assert select_dev_case(data, "weather_short")["split"] == "dev"
    with pytest.raises(BenchmarkInputError, match="holdout"):
        select_dev_case(data, "meeting_holdout")
    with pytest.raises(BenchmarkInputError, match="not found"):
        select_dev_case(data, "unknown")


def test_call_budget_rejection():
    r = CallRecorder("متن", [])
    r.calls = [{"call": n} for n in range(128)]

    async def infer(text, *, max_output_tokens=None):
        raise AssertionError("must not run")

    with pytest.raises(BenchmarkInputError, match="call budget"):
        run(r.wrap(infer)("متن", max_output_tokens=1))


def test_cli_trace_wiring_uses_same_di_provider_and_restores_method(monkeypatch, tmp_path):
    import sys
    from types import ModuleType
    from pathlib import Path

    from benchmarks.stage10_trace import execute_async
    from benchmarks.quality_benchmark import read_json

    provider_module = ModuleType("src.infrastructure.ml.mt5_model_provider")
    service_module = ModuleType("src.core.services.summarization.long_text_summarization_service")
    injector = ModuleType("src.infrastructure.di.inject")
    bootstrap = ModuleType("src.infrastructure.di.bootstrap")
    configs = ModuleType("src.infrastructure.utils.config_reader")

    class FakeProvider:
        async def summarize_async(self, text, *, max_output_tokens=None):
            return "گزارش کوتاه " + text[:8]

    provider = FakeProvider()
    original_method = provider.summarize_async

    class FakeChunker:
        def normalize(self, text):
            return text.strip()

    class FakeService:
        _provider = provider
        _chunker = FakeChunker()

        async def summarize_async(self, text, length):
            return await self._provider.summarize_async(text, max_output_tokens=80)

    service = FakeService()
    provider_module.Mt5ModelProvider = FakeProvider
    service_module.LongTextSummarizationService = FakeService
    injector.resolve = lambda typ: provider if typ is FakeProvider else service
    bootstrap.bootstrap_di = lambda: None

    class FakeConfig:
        def get(self, key):
            assert key == "model"
            return {"revision": "abc" * 13 + "a", "no_repeat_ngram_size": 3}

    configs.ConfigReader = FakeConfig
    for name, module in (
        ("src.infrastructure.ml.mt5_model_provider", provider_module),
        ("src.core.services.summarization.long_text_summarization_service", service_module),
        ("src.infrastructure.di.inject", injector),
        ("src.infrastructure.di.bootstrap", bootstrap),
        ("src.infrastructure.utils.config_reader", configs),
    ):
        monkeypatch.setitem(sys.modules, name, module)

    output = tmp_path / "trace.json"
    run(execute_async(DATASET, "weather_short", "medium", output))
    report = read_json(output)
    assert report["successful"] is True
    assert report["calls"][0]["max_output_tokens"] == 80
    assert len(report["calls"]) == 1
    assert report["no_repeat_ngram_size"] == 3
    # Bounded diagnostics only. No original text or resulting summary is serialized.
    raw = output.read_text(encoding="utf-8")
    assert "سازمان هواشناسی" not in raw
    assert "گزارش کوتاه" not in raw
    assert provider.summarize_async == original_method
