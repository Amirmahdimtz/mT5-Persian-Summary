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

        @staticmethod
        def count_input_tokens(value):
            return len(value) + 1

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
        def output_token_budget(length):
            assert length == "medium"
            return 500

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


def test_preview_lead_prose_recovers_intro_facts_without_model_generation(monkeypatch):
    mod, run, case, provider, written, _ = setup_audit(monkeypatch)
    source = (
        "# راهنمای قابلیت‌ها\n"
        "> **Development approach:** هشت مرحله متوالی، قابل بررسی\n"
        "## 1. هدف\n"
        "کاربر بتواند متن مستقیم یا فایل‌های TXT، PDF و DOCX را ارسال کند. "
        "چند فایل در یک درخواست نیز پشتیبانی می‌شوند.\n"
        "- این سطر باید در لیست فعلی بماند.\n"
        "## 2. خارج از محدوده\n"
        "- OCR تصاویر در Backlog است.\n"
    )
    candidates = mod.lead_prose_candidates(source)
    assert any("هشت مرحله متوالی" in x for x in candidates)
    assert any("TXT، PDF و DOCX" in x for x in candidates)
    assert any("چند فایل در یک درخواست" in x for x in candidates)
    assert all("OCR" not in x for x in candidates)
    assert all("این سطر" not in x for x in candidates)
    assert provider.calls == 0
    report = mod.audit_case(
        {"id": "test-case", "text": source, "facts": [
            {"id": "multi_file", "source_quote": "چند فایل در یک درخواست نیز پشتیبانی می‌شوند"},
        ]},
        "", [source], lambda _: [], set(), lead_prose=candidates,
    )
    assert report["facts"][0]["found_in_selected_clauses"] is False
    assert report["facts"][0]["found_in_lead_prose_preview"] is True
    assert report["lead_prose_candidate_count"] == len(candidates)


def test_real_mvp_pinned_facts_are_in_lead_prose_preview(monkeypatch):
    mod, *_ = setup_audit(monkeypatch)
    root = Path(__file__).resolve().parents[1]
    text = (root / "IMPLEMENTATION_PLAN.md").read_text(encoding="utf-8")
    manifest = json.loads(
        (root / "benchmarks/fixtures/real_project_documents_v1.json").read_text(encoding="utf-8")
    )
    case = next(x for x in manifest["cases"] if x["id"] == "real_mvp_plan")
    candidates = mod.lead_prose_candidates(text)
    assert len(candidates) < 32
    assert {f["id"] for f in case["facts"] if any(f["source_quote"] in s for s in candidates)} == {
        "file_formats", "multi_file", "eight_stages",
    }
    assert not any("OCR برای PDFهای اسکن‌شده" in c for c in candidates)


def test_preview_integrated_is_metadata_only_and_opt_in(monkeypatch, tmp_path):
    mod, run, case, provider, written, _ = setup_audit(monkeypatch)
    case["text"] = "## 1. هدف\nاین قانون باید اجرا شود.\n## 2. خارج از محدوده\n- ویژگی آینده باید فعال شود."
    asyncio.run(mod.execute_async(
        Path("dataset"), Path("runs"), tmp_path / "report.json",
        preview_lead_prose=True,
    ))
    assert written["inference_calls"] == 0
    assert written["preview_lead_prose"] is True
    assert written["results"][0]["lead_prose_candidate_count"] == 1
    assert written["results"][0]["facts"][0]["found_in_lead_prose_preview"] is True
    assert "این قانون" not in json.dumps(written, ensure_ascii=False)
    assert provider.calls == 0


def test_preview_flag_rejects_non_boolean(monkeypatch, tmp_path):
    mod, run, case, provider, written, Invalid = setup_audit(monkeypatch)
    with pytest.raises(Invalid, match="boolean"):
        asyncio.run(mod.execute_async(
            Path("dataset"), Path("runs"), tmp_path / "report.json",
            preview_lead_prose="yes",
        ))
    assert not written
    assert provider.calls == 0


def test_preflight_prioritizes_source_signals_and_uses_joint_token_count(monkeypatch):
    mod, run, case, provider, written, Invalid = setup_audit(monkeypatch)
    lines = [
        "متن مقدمه بدون نشانه خاص و کاملاً عمومی درباره پروژه.",
        "مدل می‌تواند متن و فایل‌های `TXT`، `PDF` و `DOCX` را تحلیل کند.",
        "سه بخش اصلی برای گزارش تدوین شده‌اند.",
        "چند گزارش در یک درخواست نیز پشتیبانی می‌شوند.",
    ]
    selected, count = mod.lead_prose_budget_preflight(
        lines, lambda text: len(text) + 1, max_tokens=500,
    )
    assert len(selected) == 3
    assert lines[1] in selected and lines[2] in selected and lines[3] in selected
    assert lines[0] not in selected
    assert count == len("\n".join(selected)) + 1


def test_preflight_rejects_invalid_tokenizer_or_budget(monkeypatch):
    mod, *_ = setup_audit(monkeypatch)
    with pytest.raises(mod.BenchmarkInputError, match="budget"):
        mod.lead_prose_budget_preflight(["نمونه `PDF`"], len, 0)
    with pytest.raises(mod.BenchmarkInputError, match="tokenizer"):
        mod.lead_prose_budget_preflight(["بررسی `PDF` ضروری است."], lambda _: True, 200)


def test_budget_preflight_integration_never_saves_source_or_invokes_model(monkeypatch, tmp_path):
    mod, run, case, provider, written, Invalid = setup_audit(monkeypatch)
    case["text"] = (
        "## 1. هدف\n"
        "ارسال فایل‌های `TXT` و `PDF` پشتیبانی می‌شود.\n"
        "## 2. خارج از محدوده\n"
        "- قابلیت آینده باید فعال شود.\n"
    )
    case["facts"] = [{
        "id": "formats",
        "source_quote": "ارسال فایل‌های `TXT` و `PDF` پشتیبانی می‌شود.",
    }]
    asyncio.run(mod.execute_async(
        Path("dataset"), Path("runs"), tmp_path / "preflight.json",
        preview_lead_prose=True, preview_lead_budget=True,
    ))
    assert provider.calls == 0
    assert written["inference_calls"] == 0
    assert written["preview_lead_budget"] is True
    result = written["results"][0]
    assert result["lead_budget_preflight"]["selected_source_sentence_count"] == 1
    assert result["facts"][0]["found_in_budgeted_lead_preflight"] is True
    assert "ارسال فایل‌های" not in json.dumps(written, ensure_ascii=False)


def test_preflight_requires_prose_preview_and_boolean_flag(monkeypatch, tmp_path):
    mod, run, case, provider, written, Invalid = setup_audit(monkeypatch)
    with pytest.raises(Invalid, match="requires"):
        asyncio.run(mod.execute_async(
            Path("dataset"), Path("runs"), tmp_path / "not-created.json",
            preview_lead_budget=True,
        ))
    with pytest.raises(Invalid, match="booleans"):
        asyncio.run(mod.execute_async(
            Path("dataset"), Path("runs"), tmp_path / "not-created.json",
            preview_lead_prose=True, preview_lead_budget="yes",
        ))
    assert provider.calls == 0
    assert not written


def test_reference_quote_floor_counts_joint_encoded_text_and_redacts_source(monkeypatch):
    mod, run, case, provider, written, Invalid = setup_audit(monkeypatch)
    facts = [
        {"id": "first", "source_quote": "فایل‌های TXT و PDF"},
        {"id": "second", "source_quote": "چند فایل در یک درخواست"},
    ]
    result = mod.reference_quote_budget_floor(
        facts, lambda value: len(value) + 1, 80,
    )
    assert result["reference_quote_count"] == 2
    assert result["combined_source_quote_tokens"] == len(
        "\n".join(f["source_quote"] for f in facts)
    ) + 1
    assert result["combined_quotes_fit_final_budget"] is True
    assert [x["fact_id"] for x in result["individual_source_quote_tokens"]] == [
        "first", "second",
    ]
    encoded = json.dumps(result, ensure_ascii=False)
    assert "چند فایل" not in encoded
    assert "TXT" not in encoded
    assert provider.calls == 0


def test_reference_quote_floor_is_not_a_model_or_summary_safety_gate(monkeypatch, tmp_path):
    mod, run, case, provider, written, Invalid = setup_audit(monkeypatch)
    case["facts"] = [
        {"id": "required", "source_quote": "این قانون باید اجرا شود."},
    ]
    asyncio.run(mod.execute_async(
        Path("dataset"), Path("runs"), tmp_path / "floor.json",
        preview_lead_prose=True, preview_lead_budget=True,
        preview_reference_floor=True,
    ))
    floor = written["results"][0]["reference_budget_floor"]
    assert floor["combined_quotes_fit_final_budget"] is True
    assert written["inference_calls"] == 0
    assert written["preview_reference_floor"] is True
    assert provider.calls == 0
    assert "این قانون" not in json.dumps(written, ensure_ascii=False)


def test_reference_floor_requires_budget_preview_and_rejects_invalid_counts(monkeypatch, tmp_path):
    mod, run, case, provider, written, Invalid = setup_audit(monkeypatch)
    with pytest.raises(Invalid, match="requires lead budget"):
        asyncio.run(mod.execute_async(
            Path("dataset"), Path("runs"), tmp_path / "missing.json",
            preview_reference_floor=True,
        ))
    with pytest.raises(Invalid, match="booleans"):
        asyncio.run(mod.execute_async(
            Path("dataset"), Path("runs"), tmp_path / "bad.json",
            preview_lead_prose=True, preview_lead_budget=True,
            preview_reference_floor=1,
        ))
    with pytest.raises(Invalid, match="tokenizer"):
        mod.reference_quote_budget_floor(
            [{"id": "number", "source_quote": "متن اصلی"}],
            lambda _: True, 80,
        )
    with pytest.raises(Invalid, match="nonempty"):
        mod.reference_quote_budget_floor(
            [{"id": "number", "source_quote": ""}], lambda _: 2, 80,
        )
    assert provider.calls == 0
    assert not written
