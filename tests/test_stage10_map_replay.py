"""Isolated deterministic offline replay tests; no tokenizer/model download."""

from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "benchmarks" / "stage10_map_replay.py"


def setup_replay(monkeypatch):
    qa = ModuleType("benchmarks.quality_benchmark")
    trace = ModuleType("benchmarks.stage10_trace")
    project = ModuleType("benchmarks")
    project.__path__ = [str(SCRIPT.parent)]

    class Invalid(ValueError):
        pass

    qa.BenchmarkInputError = Invalid
    qa.dataset_hash = lambda path: "sha-dev-abc"
    source = "- قانون باید اجرا شود.\n- روش ۱۲۳ تصویب شد.\n" * 4
    original = "خلاصه"
    probe = {
        "dataset_sha256": "sha-dev-abc", "case_id": "case-1", "split": "dev", "stage": "first_map_only",
        "first_map_generated_text": original, "first_chunk_characters": len(source),
        "chunk_count": 2, "max_output_tokens": 120, "model_revision": "pin-1", "no_repeat_ngram_size": 3,
    }
    paths = {"dataset": {"cases": []}, "probe": probe}
    qa.read_json = lambda path: paths[str(path)]
    written = {}
    qa.write_json = lambda path, obj: written.update(obj)
    trace.select_dev_case = lambda data, case_id: {
        "id": case_id, "split": "dev", "text": source + "SECOND",
        "facts": [
            {"id": "must", "source_quote": "قانون باید اجرا شود."},
            {"id": "number", "source_quote": "روش ۱۲۳ تصویب شد."},
        ],
    }

    class Provider:
        max_output_tokens = 120
        calls = 0
        def count_input_tokens(self, value):
            return len(value) + 1
        async def summarize_async(self, *args, **kwargs):
            self.calls += 1
            raise AssertionError("model must not be called")

    provider = Provider()

    class Chunker:
        def normalize(self, value):
            return value
        def chunk(self, text):
            return [source, "SECOND"]

    class Service:
        _provider = provider
        _chunker = Chunker()
        def _evidence_lines(self, text):
            assert text == source
            return ["قانون باید اجرا شود.", "روش ۱۲۳ تصویب شد."]
        async def _augment_map_async(self, chunk, text):
            return text + "\nقانون باید اجرا شود.\nروش ۱۲۳ تصویب شد."

    service = Service()
    ls = ModuleType("src.core.services.summarization.long_text_summarization_service")
    ls.LongTextSummarizationService = Service
    ml = ModuleType("src.infrastructure.ml.mt5_model_provider")
    ml.Mt5ModelProvider = Provider
    di = ModuleType("src.infrastructure.di.inject")
    di.resolve = lambda cls: provider if cls is Provider else service
    boot = ModuleType("src.infrastructure.di.bootstrap")
    boot.bootstrap_di = lambda: None
    conf = ModuleType("src.infrastructure.utils.config_reader")
    class Config:
        def get(self, key):
            return {"revision":"pin-1","no_repeat_ngram_size":3}
    conf.ConfigReader = Config

    for name, item in (
        ("benchmarks", project), ("benchmarks.quality_benchmark", qa),
        ("benchmarks.stage10_trace", trace),
        ("src.core.services.summarization.long_text_summarization_service", ls),
        ("src.infrastructure.ml.mt5_model_provider", ml),
        ("src.infrastructure.di.inject", di),
        ("src.infrastructure.di.bootstrap", boot),
        ("src.infrastructure.utils.config_reader", conf),
    ):
        monkeypatch.setitem(sys.modules, name, item)
    spec = importlib.util.spec_from_file_location("stage10_map_replay_test_module", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, probe, written, provider, Invalid


def test_replay_tracks_exact_source_facts_without_generating_or_persisting_text(monkeypatch, tmp_path):
    mod, probe, written, provider, _ = setup_replay(monkeypatch)
    asyncio.run(mod.execute_async(Path("dataset"), Path("probe"), tmp_path / "result.json"))
    assert written["stage"] == "first_map_evidence_replay"
    assert written["inference_calls"] == 0
    assert provider.calls == 0
    assert written["selected_source_lines"] == 2
    assert written["appended_source_lines"] == 2
    assert written["output_changed_by_preservation"] is True
    assert written["fact_ids_in_replayed_map_output"] == ["must", "number"]
    assert "قانون" not in json.dumps(written, ensure_ascii=False)
    assert "روش ۱۲۳" not in json.dumps(written, ensure_ascii=False)
    assert "first_map_generated_text" not in written


def test_reject_mismatched_input_hash_before_model_setup(monkeypatch, tmp_path):
    mod, probe, written, provider, Invalid = setup_replay(monkeypatch)
    probe["dataset_sha256"] = "wrong"
    with pytest.raises(Invalid, match="does not match"):
        asyncio.run(mod.execute_async(Path("dataset"), Path("probe"), tmp_path / "result.json"))
    assert not written


def test_output_exists_is_not_overwritten(monkeypatch, tmp_path):
    mod, probe, written, provider, Invalid = setup_replay(monkeypatch)
    output = tmp_path / "existing.json"
    output.write_text("preserved", encoding="utf-8")
    with pytest.raises(Invalid, match="already exists"):
        asyncio.run(mod.execute_async(Path("dataset"), Path("probe"), output))
    assert output.read_text(encoding="utf-8") == "preserved"


def test_invalid_first_map_metadata_fails_closed(monkeypatch, tmp_path):
    mod, probe, written, provider, Invalid = setup_replay(monkeypatch)
    probe["max_output_tokens"] = "120"
    with pytest.raises(Invalid, match="token ceiling"):
        asyncio.run(mod.execute_async(Path("dataset"), Path("probe"), tmp_path / "result.json"))


def test_different_checkpoint_is_rejected(monkeypatch, tmp_path):
    mod, probe, written, provider, Invalid = setup_replay(monkeypatch)
    probe["model_revision"] = "wrong-revision"
    with pytest.raises(Invalid, match="requires the original"):
        asyncio.run(mod.execute_async(Path("dataset"), Path("probe"), tmp_path / "result.json"))
