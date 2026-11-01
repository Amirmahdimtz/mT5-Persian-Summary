"""Compare fixed-dataset Stage 9 and Stage 10 raw model runs.

This measures observable output differences, not factual accuracy. Review the
candidate's atomic claims and expected facts separately before any GO decision.
No model load, HTTP service dependency or network access is required.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from benchmarks.quality_benchmark import (
    BenchmarkInputError,
    dataset_hash,
    duplicate_fourgram_fraction,
    read_json,
    runs_hash,
    validate_dataset,
    write_json,
)


def _index_runs(data: dict[str, Any], valid_ids: set[str], expected_sha: str) -> dict[tuple[str, str], dict[str, Any]]:
    if data.get("dataset_sha256") != expected_sha:
        raise BenchmarkInputError("run dataset SHA does not match the supplied fixed dataset")
    results = data.get("results")
    if not isinstance(results, list) or not results:
        raise BenchmarkInputError("run must contain at least one result")
    indexed: dict[tuple[str, str], dict[str, Any]] = {}
    for result in results:
        if not isinstance(result, dict):
            raise BenchmarkInputError("invalid run result")
        key = (result.get("case_id"), result.get("summary_length"))
        if key[0] not in valid_ids or key[1] not in {"short", "medium", "long"} or key in indexed:
            raise BenchmarkInputError("invalid, duplicate or unknown case/length key")
        if result.get("error_code"):
            if not isinstance(result["error_code"], str) or not result["error_code"].strip():
                raise BenchmarkInputError("invalid run error_code")
        elif not isinstance(result.get("summary"), str) or not result["summary"].strip():
            raise BenchmarkInputError("successful run must contain a nonempty summary")
        indexed[key] = result
    return indexed


def compare_runs(dataset: dict[str, Any], expected_sha: str, baseline: dict[str, Any],
                 candidate: dict[str, Any]) -> dict[str, Any]:
    cases = validate_dataset(dataset)
    known = {c["id"] for c in cases}
    base = _index_runs(baseline, known, expected_sha)
    cand = _index_runs(candidate, known, expected_sha)
    if set(base) != set(cand):
        raise BenchmarkInputError("baseline and candidate must contain identical case/length keys")

    comparison = []
    for case_id, tier in sorted(base):
        old, new = base[(case_id, tier)], cand[(case_id, tier)]
        old_text = old.get("summary") if not old.get("error_code") else None
        new_text = new.get("summary") if not new.get("error_code") else None
        comparison.append({
            "case_id": case_id,
            "summary_length": tier,
            "baseline_error": old.get("error_code"),
            "candidate_error": new.get("error_code"),
            "outputs_identical": old_text == new_text if old_text is not None and new_text is not None else None,
            "baseline_chars": len(old_text) if old_text is not None else None,
            "candidate_chars": len(new_text) if new_text is not None else None,
            "baseline_repeated_fourgram_fraction": (
                duplicate_fourgram_fraction(old_text) if old_text is not None else None
            ),
            "candidate_repeated_fourgram_fraction": (
                duplicate_fourgram_fraction(new_text) if new_text is not None else None
            ),
            "baseline_seconds": old.get("elapsed_seconds"),
            "candidate_seconds": new.get("elapsed_seconds"),
            "baseline_tokens_including_specials": old.get("output_tokens_including_specials"),
            "candidate_tokens_including_specials": new.get("output_tokens_including_specials"),
        })

    baseline_params = baseline.get("model_settings")
    candidate_params = candidate.get("model_settings")
    return {
        "dataset_sha256": expected_sha,
        "baseline_runs_sha256": runs_hash(baseline),
        "candidate_runs_sha256": runs_hash(candidate),
        "paired_cases": len(comparison),
        "baseline_generation": baseline_params if isinstance(baseline_params, dict) else None,
        "candidate_generation": candidate_params if isinstance(candidate_params, dict) else None,
        "different_successful_outputs": sum(x["outputs_identical"] is False for x in comparison),
        "unchanged_successful_outputs": sum(x["outputs_identical"] is True for x in comparison),
        "comparison": comparison,
        "semantic_review_status": "NOT_REVIEWED",
        "stage10_quality_gate": "NOT_EVALUATED",
        "limitations": (
            "Raw output length/repetition/timing do not establish factual improvement, "
            "hallucination avoidance, length adherence or statistically valid latency. "
            "Review atomic claims and expected facts before any Stage 10 GO decision."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        dataset = read_json(args.dataset)
        report = compare_runs(
            dataset, dataset_hash(args.dataset),
            read_json(args.baseline), read_json(args.candidate),
        )
        write_json(args.output, report)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        parser.exit(2, f"Stage 10 comparison failed: {type(error).__name__}: {error}\n")
    print(
        f"Saved Stage 10 raw comparison: {args.output}; "
        f"paired={report['paired_cases']} changed={report['different_successful_outputs']}; "
        "semantic quality NOT REVIEWED"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
