"""Stage 9 benchmark tests; no real model download or network required."""

from __future__ import annotations

import asyncio
import copy
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

from benchmarks.quality_benchmark import (
    BenchmarkInputError,
    DATASET,
    create_review_template,
    dataset_hash,
    execute_async,
    read_json,
    runs_hash,
    score_reviews,
    validate_dataset,
    write_json,
)


def sample_run() -> tuple[dict, dict, dict]:
    dataset = read_json(DATASET)
    case = validate_dataset(dataset)[0]
    run = {"dataset_sha256": dataset_hash(DATASET), "results": [
        {"case_id": case["id"], "summary_length": "medium", "summary": case["reference_summary"]}
    ]}
    review = create_review_template(dataset, run)
    for index, fact in enumerate(review["reviews"][0]["facts"]):
        fact["label"] = "covered" if index == 0 else "omitted"
    review["reviews"][0]["claims"] = [
        {"claim": "بارش بیشتر می‌شود", "supported": True,
         "evidence_quote": case["facts"][0]["source_quote"]},
        {"claim": "جلسه لغو شد", "supported": False, "evidence_quote": None},
    ]
    return dataset, run, review


def test_dataset_cases_have_exact_source_evidence():
    cases = validate_dataset(read_json(DATASET))
    assert len(cases) == 7
    assert {x["split"] for x in cases} == {"dev", "holdout"}
    assert any(x["category"] == "multitopic" for x in cases)
    assert any(x["category"] == "long_repetitive" for x in cases)
    assert any(x["category"] == "meeting" for x in cases)


@pytest.mark.parametrize("mutation", [
    lambda d: d["cases"][0].update(id="invalid id"),
    lambda d: d["cases"][0].update(split="test"),
    lambda d: d["cases"][0].update(repeat=51),
    lambda d: d["cases"][0]["facts"][0].update(source_quote="unrelated quote"),
    lambda d: d["cases"][0]["facts"][0].update(type=["topic"]),
    lambda d: d["cases"].append(copy.deepcopy(d["cases"][0])),
    lambda d: d["cases"][0]["facts"].append(copy.deepcopy(d["cases"][0]["facts"][0])),
    lambda d: d.update(license="proprietary"),
])
def test_reject_inconsistent_dataset(mutation):
    data = read_json(DATASET)
    mutation(data)
    with pytest.raises(BenchmarkInputError):
        validate_dataset(data)


def test_template_is_unreviewed_and_scores_fail_closed():
    dataset, run, review = sample_run()
    template = create_review_template(dataset, run)
    assert template["reviews"][0]["facts"][0]["label"] is None
    with pytest.raises(BenchmarkInputError, match="unlabeled"):
        score_reviews(dataset, run, template, expected_hash=dataset_hash(DATASET))


def test_manual_scores_distinguish_covered_omitted_and_unsupported_claims():
    dataset, run, review = sample_run()
    report = score_reviews(dataset, run, review, expected_hash=dataset_hash(DATASET))
    assert report["reviewed_runs"] == 1
    assert report["unreviewed_successful_runs"] == 0
    assert report["fact_coverage"] == 0.5
    assert report["unsupported_claim_rate"] == 0.5
    assert report["claims_reviewed"] == 2
    assert report["length_diagnostics"]["medium"]["count"] == 1


def test_partial_reviews_are_reported_as_partial_not_full():
    dataset, run, review = sample_run()
    run["results"].append({"case_id": "meeting_decisions", "summary_length": "short", "summary": "جلسه"})
    review["runs_sha256"] = runs_hash(run)
    report = score_reviews(dataset, run, review, expected_hash=dataset_hash(DATASET))
    assert report["unreviewed_successful_runs"] == 1


@pytest.mark.parametrize("mutation", [
    lambda d, r, v: v.update(dataset_sha256="000"),
    lambda d, r, v: v.update(runs_sha256="000"),
    lambda d, r, v: v["reviews"][0]["claims"][0].update(evidence_quote="invented"),
    lambda d, r, v: v["reviews"][0]["claims"][1].update(evidence_quote="not allowed"),
    lambda d, r, v: v["reviews"][0]["facts"][0].update(label="guessed"),
    lambda d, r, v: v["reviews"][0]["facts"].pop(),
    lambda d, r, v: v["reviews"][0].update(claims=[]),
    lambda d, r, v: r["results"].append(copy.deepcopy(r["results"][0])),
])
def test_reject_invalid_or_forged_reviews(mutation):
    data, runs, reviews = sample_run()
    mutation(data, runs, reviews)
    with pytest.raises(BenchmarkInputError):
        score_reviews(data, runs, reviews, expected_hash=dataset_hash(DATASET))


def test_write_does_not_overwrite_existing_result(tmp_path):
    target = tmp_path / "baseline.json"
    write_json(target, {"first": True})
    with pytest.raises(FileExistsError):
        write_json(target, {"first": False})
    assert read_json(target) == {"first": True}


def test_cli_validate_runs_without_model_dependencies():
    completed = subprocess.run(
        [sys.executable, "-m", "benchmarks.quality_benchmark", "validate"],
        cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, check=True,
    )
    assert "VALID: 7 cases" in completed.stdout


def test_model_execution_wiring_with_fake_backend(monkeypatch, tmp_path):
    model_module = ModuleType("src.infrastructure.ml.mt5_model_provider")
    class FakeProvider:
        @staticmethod
        def count_input_tokens(value):
            return len(value.split()) + 1
    model_module.Mt5ModelProvider = FakeProvider
    service_module = ModuleType("src.core.services.summarization.long_text_summarization_service")
    class FakeService:
        def __init__(self):
            self.map_trial_flags = []
            self.final_trial_flags = []

        async def summarize_async(
            self, text, summary_length, *,
            preserve_map_evidence=False, source_grounded_final=False
        ):
            self.map_trial_flags.append(preserve_map_evidence)
            self.final_trial_flags.append(source_grounded_final)
            return f"خلاصه {summary_length}"
    service_module.LongTextSummarizationService = FakeService
    fake_service = FakeService()
    inject_module = ModuleType("src.infrastructure.di.inject")
    inject_module.resolve = lambda cls: FakeProvider() if cls is FakeProvider else fake_service
    bootstrap_module = ModuleType("src.infrastructure.di.bootstrap")
    bootstrap_module.bootstrap_di = lambda: None
    config_module = ModuleType("src.infrastructure.utils.config_reader")
    class FakeConfig:
        def get(self, key):
            assert key == "model"
            return {"id": "test-only", "secret_access_token": "must-not-leak"}
    config_module.ConfigReader = FakeConfig
    for name, value in (
        ("src.infrastructure.ml.mt5_model_provider", model_module),
        ("src.core.services.summarization.long_text_summarization_service", service_module),
        ("src.infrastructure.di.inject", inject_module),
        ("src.infrastructure.di.bootstrap", bootstrap_module),
        ("src.infrastructure.utils.config_reader", config_module),
    ):
        monkeypatch.setitem(sys.modules, name, value)
    result_file = tmp_path / "result.json"
    asyncio.run(execute_async(DATASET, result_file, ["medium"], "dev"))
    result = read_json(result_file)
    assert len(result["results"]) == 5
    assert all(x["summary"] == "خلاصه medium" for x in result["results"])
    assert all(x["output_tokens_including_specials"] == 3 for x in result["results"])
    assert result["model_settings"] == {"id": "test-only"}
    assert result["pipeline_settings"] == {
        "preserve_map_evidence": False, "source_grounded_final": False,
    }
    assert result["dataset_sha256"] == dataset_hash(DATASET)

    trial_file = tmp_path / "map_evidence_trial.json"
    asyncio.run(execute_async(
        DATASET, trial_file, ["medium"], "dev", preserve_map_evidence=True
    ))
    trial = read_json(trial_file)
    assert trial["pipeline_settings"] == {
        "preserve_map_evidence": True, "source_grounded_final": False,
    }
    assert len(trial["results"]) == 5
    assert fake_service.map_trial_flags == [False] * 5 + [True] * 5
    assert fake_service.final_trial_flags == [False] * 10

    final_file = tmp_path / "final_evidence_trial.json"
    asyncio.run(execute_async(
        DATASET, final_file, ["medium"], "dev",
        preserve_map_evidence=True, source_grounded_final=True,
    ))
    final = read_json(final_file)
    assert final["pipeline_settings"] == {
        "preserve_map_evidence": True, "source_grounded_final": True,
    }
    assert len(final["results"]) == 5
    assert fake_service.final_trial_flags == [False] * 10 + [True] * 5


def test_repetition_diagnostics_distinguish_repeated_word_sequences():
    from benchmarks.quality_benchmark import duplicate_fourgram_fraction

    repeated = "برای استفاده با چتGPT برای استفاده با چتGPT طراحی شد"
    clean = "جلسه ۱۴ آبان با حضور نمایندگان برگزار شد و بودجه تصویب شد"
    assert duplicate_fourgram_fraction(repeated) > 0.0
    assert duplicate_fourgram_fraction(clean) == 0.0
    assert duplicate_fourgram_fraction("متن کوتاه") == 0.0


def test_scoring_reports_output_token_ceiling_and_repetition_without_model():
    dataset, runs, review = sample_run()
    runs["model_settings"] = {"max_output_tokens": 120}
    output = "این متن برای استفاده در چتGPT برای استفاده در چتGPT نوشته شد"
    runs["results"][0]["summary"] = output
    runs["results"][0]["output_tokens_including_specials"] = 21
    review["runs_sha256"] = runs_hash(runs)
    scored = score_reviews(dataset, runs, review, expected_hash=dataset_hash(DATASET))
    assert scored["length_diagnostics"]["medium"]["configured_token_ceiling"] == 80
    assert scored["length_diagnostics"]["medium"]["mean_output_tokens_including_specials"] == 21
    assert scored["length_diagnostics"]["medium"]["outputs_exceeding_ceiling"] == 0
    assert scored["repetition_diagnostics"]["medium"]["outputs_with_repeated_fourgrams"] == 1
    assert scored["repetition_diagnostics"]["long"]["mean_duplicate_fourgram_fraction"] is None


def test_score_does_not_assume_missing_token_counts_pass_length_budget():
    dataset, runs, review = sample_run()
    scored = score_reviews(dataset, runs, review, expected_hash=dataset_hash(DATASET))
    tier = scored["length_diagnostics"]["medium"]
    assert tier["configured_token_ceiling"] is None
    assert tier["outputs_exceeding_ceiling"] is None
    assert tier["mean_output_tokens_including_specials"] is None
