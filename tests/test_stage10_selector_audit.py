"""Pure fake-model Stage 10 selector audit tests; no mT5/network use."""
from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "benchmarks" / "stage10_selector_audit.py"


def setup_audit(monkeypatch):
    benchmarks = ModuleType("benchmarks")
    benchmarks.__path__ = [str(SCRIPT.parent)]
    qa = ModuleType("benchmarks.quality_benchmark")
    trace = ModuleType("benchmarks.stage10_trace")

    class Invalid(ValueError):
        pass

    qa.BenchmarkInputError = Invalid
    qa.dataset_hash = lambda path: "dataset-v1"
    qa.runs_hash = lambda run: "runs-v1"
    qa.write_json = lambda path, report: written.update(report)
    selected_case = {
        "id": "dev-case", "split": "dev",
        "text": "## Scope\n- این قانون باید اجرا شود.\n## Out of scope\n- ویژگی آینده باید فعال شود.",
        "facts": [
            {"id": "required", "source_quote": "این قانون باید اجرا شود."},
            {"id": "unsupported", "source_quote": "ویژگی آینده باید فعال شود."},
            {"id": "prose_missing", "source_quote": "Scope"},
        ],
    }
    run = {
        "dataset_sha256": "dataset-v1", "split": "dev",
        "pipeline_settings": {"preserve_map_evidence": True, "source_grounded_final": True},
        "model_settings": {"revision": "pinned", "no_repeat_ngram_size": 3},
        "results": [{"case_id": "dev-case", "summary_length": "medium", "summary": "این قانون باید اجرا شود."}],
    }
    data = {"case": selected_case}
    mapping = {"dataset": data, "runs": run}
    written = {}
    qa.read_json = lambda path: mapping[str(path)]
    trace.select_dev_case = lambda data, id: selected_case if id == "dev-case" and selected_case["split"] == "dev" else (_ for _ in ()).throw(Invalid("holdout not allowed"))

    class FakeProvider:
        calls = 0
        async def summarize_async(self, *args, **kwargs):
            self.calls += 1
            raise AssertionError("model inference must never run")

    provider = FakeProvider()

    class FakeChunker:
        def normalize(self, value):
            return value
        def chunk(self, text):
            return text.split("\n## Out of scope") if "\n## Out of scope" in text else [text]

    class FakeService:
        _provider = provider
        _chunker = FakeChunker()

        @staticmethod
        def _evidence_lines(chunk):
            if "این قانون باید اجرا شود." in chunk:
                return ["این قانون باید اجرا شود."]
            return ["ویژگی آینده باید فعال شود."]

        @staticmethod
        def _excluded_original_clauses(source):
            return {"ویژگی آینده باید فعال شود."}

    service = FakeService()
    ls = ModuleType("src.core.services.summarization.long_text_summarization_service")
    ls.LongTextSummarizationService = FakeService
    ml = ModuleType("src.infrastructure.ml.mt5_model_provider")
    ml.Mt5ModelProvider = FakeProvider
    di = ModuleType("src.infrastructure.di.inject")
    di.resolve = lambda typ: provider if typ is FakeProvider else service
    bootstrap = ModuleType("src.infrastructure.di.bootstrap")
    bootstrap.bootstrap_di = lambda: None
    config = ModuleType("src.infrastructure.utils.config_reader")
    class FakeConfig:
        def get(self, key):
            return {"revision": "pinned", "no_repeat_ngram_size": 3}
    config.ConfigReader = FakeConfig
    for name, item in (
        ("benchmarks", benchmarks),
        ("benchmarks.quality_benchmark", qa),
        ("benchmarks.stage10_trace", trace),
        ("src.core.services.summarization.long_text_summarization_service", ls),
        ("src.infrastructure.ml.mt5_model_provider", ml),
        ("src.infrastructure.di.inject", di),
        ("src.infrastructure.di.bootstrap", bootstrap),
        ("src.infrastructure.utils.config_reader", config),
    ):
        monkeypatch.setitem(sys.modules, name, item)
    spec = importlib.util.spec_from_file_location("audit_standalone_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module, run, selected_case, provider, written, Invalid


def test_lexical_eligibility_distinguishes_scoped_candidates(monkeypatch):
    mod, run, case, provider, written, Invalid = setup_audit(monkeypatch)
    output = mod.audit_case(
        case, "این قانون باید اجرا شود.", ["source", "other"],
        lambda c: ["این قانون باید اجرا شود.", "ویژگی آینده باید فعال شود."],
        {"ویژگی آینده باید فعال شود."},
    )
    facts = {r["fact_id"]: r for r in output["facts"]}
    assert facts["required"]["found_in_eligible_clauses"] is True
    assert facts["required"]["found_in_final_output_verbatim"] is True
    assert facts["unsupported"]["found_in_selected_clauses"] is True
    assert facts["unsupported"]["found_in_excluded_clauses"] is True
    assert facts["unsupported"]["found_in_eligible_clauses"] is False
    assert facts["prose_missing"]["found_in_original_source"] is True
    assert facts["prose_missing"]["found_in_selected_clauses"] is False
    assert "این قانون" not in json.dumps(output, ensure_ascii=False)


def test_end_to_end_audit_has_no_inference_and_redacts_text(monkeypatch, tmp_path):
    mod, run, case, provider, written, Invalid = setup_audit(monkeypatch)
    asyncio.run(mod.execute_async(Path("dataset"), Path("runs"), tmp_path / "audit.json"))
    assert written["stage"] == "stage10_offline_selector_audit"
    assert written["inference_calls"] == 0
    assert provider.calls == 0
    assert len(written["results"]) == 1
    assert written["results"][0]["facts"][0]["found_in_eligible_clauses"] is True
    assert "ویژگی آینده" not in json.dumps(written, ensure_ascii=False)
    assert "خلاصه" not in json.dumps(written, ensure_ascii=False)


def test_dataset_mismatch_and_output_exists_fail_closed(monkeypatch, tmp_path):
    mod, run, case, provider, written, Invalid = setup_audit(monkeypatch)
    run["dataset_sha256"] = "wrong"
    with pytest.raises(Invalid, match="hash"):
        asyncio.run(mod.execute_async(Path("dataset"), Path("runs"), tmp_path / "audit.json"))
    assert not written
    run["dataset_sha256"] = "dataset-v1"
    target = tmp_path / "audit.json"
    target.write_text("do not overwrite", encoding="utf-8")
    with pytest.raises(Invalid, match="already exists"):
        asyncio.run(mod.execute_async(Path("dataset"), Path("runs"), target))
    assert target.read_text(encoding="utf-8") == "do not overwrite"


def test_rejects_holdout_unreviewable_and_duplicate_records(monkeypatch, tmp_path):
    mod, run, case, provider, written, Invalid = setup_audit(monkeypatch)
    run["results"][0]["summary_length"] = "long"
    with pytest.raises(Invalid, match="medium"):
        asyncio.run(mod.execute_async(Path("dataset"), Path("runs"), tmp_path / "a.json"))
    run["results"][0]["summary_length"] = "medium"
    run["results"].append(dict(run["results"][0]))
    with pytest.raises(Invalid, match="duplicate"):
        asyncio.run(mod.execute_async(Path("dataset"), Path("runs"), tmp_path / "a.json"))
    run["results"].pop()
    case["split"] = "holdout"
    with pytest.raises(Invalid, match="holdout"):
        asyncio.run(mod.execute_async(Path("dataset"), Path("runs"), tmp_path / "a.json"))
    assert provider.calls == 0


def test_rejects_missing_optin_and_wrong_revision(monkeypatch, tmp_path):
    mod, run, case, provider, written, Invalid = setup_audit(monkeypatch)
    run["pipeline_settings"]["source_grounded_final"] = False
    with pytest.raises(Invalid, match="source-grounded"):
        asyncio.run(mod.execute_async(Path("dataset"), Path("runs"), tmp_path / "audit.json"))
    run["pipeline_settings"]["source_grounded_final"] = True
    run["model_settings"]["revision"] = "wrong"
    with pytest.raises(Invalid, match="checkpoint"):
        asyncio.run(mod.execute_async(Path("dataset"), Path("runs"), tmp_path / "audit.json"))
    assert provider.calls == 0
