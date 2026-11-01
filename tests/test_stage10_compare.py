"""Stage 10 raw-comparison tests. No transformer weights or network required."""

from __future__ import annotations

import copy

import pytest

from benchmarks.quality_benchmark import BenchmarkInputError, DATASET, dataset_hash, read_json
from benchmarks.stage10_compare import compare_runs


def pair():
    dataset = read_json(DATASET)
    case = dataset["cases"][0]
    entry = {
        "case_id": case["id"],
        "summary_length": "medium",
        "summary": "بارش باران در شمال افزایش می‌یابد",
        "output_tokens_including_specials": 12,
        "elapsed_seconds": 1.5,
    }
    baseline = {"dataset_sha256": dataset_hash(DATASET), "model_settings": {"no_repeat_ngram_size": 0},
                "results": [entry]}
    candidate = copy.deepcopy(baseline)
    candidate["model_settings"]["no_repeat_ngram_size"] = 3
    candidate["results"][0]["summary"] = "بارش افزایش می‌یابد؛ رانندگان باید شرایط جاده را بررسی کنند"
    return dataset, baseline, candidate


def test_same_cases_report_output_change_not_quality_claim():
    dataset, baseline, candidate = pair()
    report = compare_runs(dataset, dataset_hash(DATASET), baseline, candidate)
    assert report["paired_cases"] == 1
    assert report["different_successful_outputs"] == 1
    assert report["unchanged_successful_outputs"] == 0
    assert report["semantic_review_status"] == "NOT_REVIEWED"
    assert report["stage10_quality_gate"] == "NOT_EVALUATED"
    assert report["comparison"][0]["baseline_chars"] < report["comparison"][0]["candidate_chars"]
    assert report["candidate_generation"]["no_repeat_ngram_size"] == 3
    assert "summary" not in report["comparison"][0]


def test_identical_text_does_not_imply_quality_gain():
    dataset, baseline, candidate = pair()
    candidate["results"][0]["summary"] = baseline["results"][0]["summary"]
    report = compare_runs(dataset, dataset_hash(DATASET), baseline, candidate)
    assert report["unchanged_successful_outputs"] == 1
    assert report["stage10_quality_gate"] == "NOT_EVALUATED"


@pytest.mark.parametrize("change", [
    lambda b, c: c.update(dataset_sha256="incorrect"),
    lambda b, c: c["results"].append(copy.deepcopy(c["results"][0])),
    lambda b, c: c["results"][0].update(case_id="not_in_dataset"),
    lambda b, c: c["results"][0].update(summary_length="unknown"),
    lambda b, c: c["results"][0].update(summary=""),
    lambda b, c: c["results"].append({"case_id": "meeting_decisions", "summary_length": "long", "summary": "جلسه"}),
    lambda b, c: c.update(results=[]),
])
def test_fail_closed_on_unpaired_or_invalid_runs(change):
    dataset, baseline, candidate = pair()
    change(baseline, candidate)
    with pytest.raises(BenchmarkInputError):
        compare_runs(dataset, dataset_hash(DATASET), baseline, candidate)


def test_missing_model_details_are_not_invented():
    dataset, baseline, candidate = pair()
    candidate.pop("model_settings")
    report = compare_runs(dataset, dataset_hash(DATASET), baseline, candidate)
    assert report["candidate_generation"] is None


def test_failed_candidate_inference_is_visible_not_silently_ignored():
    dataset, baseline, candidate = pair()
    candidate["results"][0].pop("summary")
    candidate["results"][0]["error_code"] = "ModelInferenceError"
    report = compare_runs(dataset, dataset_hash(DATASET), baseline, candidate)
    row = report["comparison"][0]
    assert row["candidate_error"] == "ModelInferenceError"
    assert row["outputs_identical"] is None
    assert report["different_successful_outputs"] == 0


def test_metadata_comparison_does_not_leak_unknown_private_fields():
    dataset, baseline, candidate = pair()
    baseline["model_settings"]["private_token"] = "do-not-echo"
    candidate["model_settings"]["api_key"] = "do-not-echo"
    report = compare_runs(dataset, dataset_hash(DATASET), baseline, candidate)
    assert "private_token" not in report["baseline_generation"]
    assert "api_key" not in report["candidate_generation"]
