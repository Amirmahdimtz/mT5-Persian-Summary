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


def test_trace_augmented_map_evidence_is_visible_before_reduce():
    from benchmarks.stage10_trace import MapEvidenceRecorder

    fact = "باید از سند اصلی حفظ شود."
    rec = CallRecorder(fact, [{"id": "critical_rule", "source_quote": fact}])
    evidence = MapEvidenceRecorder(
        [{"id": "critical_rule", "source_quote": fact}], rec.calls,
        lambda _: [fact],
    )

    async def augment(source, generated):
        assert source == fact
        return generated + "\n" + source

    async def reduce(input_text, *, max_output_tokens=None):
        assert fact in input_text
        return "خلاصه بدون قاعده"

    async def workflow():
        first = await evidence.wrap(augment)(fact, "خلاصه عمومی")
        return await rec.wrap(reduce)(first, max_output_tokens=80)

    assert run(workflow()) == "خلاصه بدون قاعده"
    event = evidence.events[0]
    assert event["selected_exact_fact_ids"] == ["critical_rule"]
    assert event["before_exact_fact_ids"] == []
    assert event["after_exact_fact_ids"] == ["critical_rule"]
    assert event["appended_source_lines"] == 1
    assert rec.calls[0]["input_contains_exact_fact_quotes"] == ["critical_rule"]
    assert rec.calls[0]["output_contains_exact_fact_quotes"] == []
    assert fact not in str(event)


def test_trace_map_augmentation_errors_do_not_leak_source_text():
    from benchmarks.stage10_trace import MapEvidenceRecorder

    quote = "موضوع محرمانه سند"
    rec = MapEvidenceRecorder(
        [{"id": "rule", "source_quote": quote}], [],
        lambda _: [quote],
    )

    async def broken(_source, _summary):
        raise RuntimeError(quote)

    with pytest.raises(RuntimeError, match=quote):
        run(rec.wrap(broken)(quote, "خلاصه"))
    assert rec.events[0]["error_code"] == "RuntimeError"
    assert quote not in str(rec.events)
    rec.MAX_EVENTS = 1
    with pytest.raises(BenchmarkInputError, match="event budget"):
        run(rec.wrap(broken)(quote, "خلاصه"))


def test_trace_dev_map_ablation_records_exact_evidence_and_restores_di(monkeypatch, tmp_path):
    import json
    import sys
    from types import ModuleType
    from benchmarks.stage10_trace import execute_async

    data = read_json(DATASET)
    case = next(c for c in data["cases"] if c["id"] == "weather_short")
    quote = case["facts"][0]["source_quote"]
    provider_module = ModuleType("src.infrastructure.ml.mt5_model_provider")
    service_module = ModuleType("src.core.services.summarization.long_text_summarization_service")
    injector = ModuleType("src.infrastructure.di.inject")
    bootstrap = ModuleType("src.infrastructure.di.bootstrap")
    config_module = ModuleType("src.infrastructure.utils.config_reader")

    class FakeProvider:
        async def summarize_async(self, value, *, max_output_tokens=None):
            return "خلاصه عمومی"

    provider = FakeProvider()
    original_provider_method = provider.summarize_async

    class FakeChunker:
        def normalize(self, text):
            return text.strip()

    class FakeService:
        _provider = provider
        _chunker = FakeChunker()

        @staticmethod
        def _evidence_lines(source):
            return [quote] if quote in source else []

        async def _augment_map_async(self, source, text):
            return text + "\n" + quote

        async def summarize_async(self, source, length, *, preserve_map_evidence=False):
            first = await self._provider.summarize_async(source, max_output_tokens=120)
            if preserve_map_evidence:
                first = await self._augment_map_async(source, first)
            return await self._provider.summarize_async(first, max_output_tokens=80)

    service = FakeService()
    original_map_method = service._augment_map_async
    provider_module.Mt5ModelProvider = FakeProvider
    service_module.LongTextSummarizationService = FakeService
    injector.resolve = lambda cls: provider if cls is FakeProvider else service
    bootstrap.bootstrap_di = lambda: None

    class FakeConfig:
        def get(self, name):
            assert name == "model"
            return {"revision": "a" * 40, "no_repeat_ngram_size": 3}

    config_module.ConfigReader = FakeConfig
    for name, module in (
        ("src.infrastructure.ml.mt5_model_provider", provider_module),
        ("src.core.services.summarization.long_text_summarization_service", service_module),
        ("src.infrastructure.di.inject", injector),
        ("src.infrastructure.di.bootstrap", bootstrap),
        ("src.infrastructure.utils.config_reader", config_module),
    ):
        monkeypatch.setitem(sys.modules, name, module)

    output = tmp_path / "local-trace.json"
    run(execute_async(DATASET, "weather_short", "medium", output, preserve_map_evidence=True))
    report = read_json(output)
    assert report["successful"] is True
    assert report["pipeline_settings"] == {"preserve_map_evidence": True}
    assert len(report["calls"]) == 2
    assert len(report["map_evidence_augmentations"]) == 1
    event = report["map_evidence_augmentations"][0]
    assert event["preceding_model_call"] == 1
    assert event["after_exact_fact_ids"] == [case["facts"][0]["id"]]
    assert event["appended_source_lines"] == 1
    assert report["calls"][1]["input_contains_exact_fact_quotes"] == [case["facts"][0]["id"]]
    assert report["calls"][1]["output_contains_exact_fact_quotes"] == []
    raw = output.read_text(encoding="utf-8")
    assert quote not in raw
    assert "خلاصه عمومی" not in raw
    assert provider.summarize_async == original_provider_method
    assert service._augment_map_async == original_map_method


def test_map_trace_requires_a_boolean_and_protects_existing_file(tmp_path):
    from benchmarks.stage10_trace import execute_async

    with pytest.raises(BenchmarkInputError, match="boolean"):
        run(execute_async(
            DATASET, "weather_short", "medium", tmp_path / "none.json",
            preserve_map_evidence=1,
        ))
    output = tmp_path / "existing.json"
    output.write_text("{}", encoding="utf-8")
    with pytest.raises(BenchmarkInputError, match="already exists"):
        run(execute_async(
            DATASET, "weather_short", "medium", output,
            preserve_map_evidence=True,
        ))
    assert output.read_text(encoding="utf-8") == "{}"
