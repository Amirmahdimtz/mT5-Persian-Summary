"""Offline Stage 13 Development-only evidence quality and resource diagnostics.

Runs the real extractive Stage 12 Service and the existing Stage 11 benchmark
without model inference, network calls, or evaluation of holdout cases.
Quote-level checks are *not* a human semantic/Production quality judgment.
"""

from __future__ import annotations

import argparse
import asyncio
import math
import statistics
import time
import tracemalloc
from pathlib import Path
from typing import Any

from benchmarks.quality_benchmark import (
    DATASET, BenchmarkInputError, dataset_hash, read_json, write_json,
)
from benchmarks.stage11_retrieval_benchmark import LABELS as STAGE11_LABELS
from benchmarks.stage11_retrieval_benchmark import evaluate as evaluate_retrieval
from src.core.services.document_query.document_query_service import DocumentQueryService
from src.core.services.summarization.document_extraction_service import DocumentExtractionService
from src.core.services.summarization.document_retrieval_service import DocumentRetrievalService

LABELS = Path(__file__).resolve().parent / "fixtures" / "stage13_query_dev_v1.json"
STATUSES = frozenset({"found", "not_found", "ambiguous"})
MODES = frozenset({"answer", "focused_summary"})


def _validate_labels(data: dict[str, Any]) -> tuple[dict[str, str], list[dict[str, Any]]]:
    if data.get("version") != 1 or data.get("split") != "dev" or data.get("license") != "CC0-1.0":
        raise BenchmarkInputError("Stage 13 fixture must be version-1 CC0 Development")
    documents, cases = data.get("documents"), data.get("cases")
    if (not isinstance(documents, list) or not 1 <= len(documents) <= 50
            or not isinstance(cases, list) or not 1 <= len(cases) <= 100):
        raise BenchmarkInputError("Stage 13 fixture documents/cases must be bounded lists")
    indexed: dict[str, str] = {}
    for item in documents:
        if not isinstance(item, dict):
            raise BenchmarkInputError("invalid Stage 13 document")
        name, value = item.get("id"), item.get("text")
        if (not isinstance(name, str) or not name.isidentifier() or not name.isascii()
                or name in indexed or not isinstance(value, str) or not value.strip()
                or len(value) > 200_000):
            raise BenchmarkInputError("invalid Stage 13 document ID/text")
        indexed[name] = value
    seen: set[str] = set()
    for item in cases:
        if not isinstance(item, dict):
            raise BenchmarkInputError("invalid Stage 13 case")
        ident, docid, query, status, mode = (
            item.get("id"), item.get("document_id"), item.get("query"),
            item.get("status"), item.get("mode"),
        )
        if (not isinstance(ident, str) or not ident.isidentifier() or not ident.isascii()
                or ident in seen or docid not in indexed
                or not isinstance(query, str) or not query.strip() or len(query) > 512
                or status not in STATUSES or mode not in MODES):
            raise BenchmarkInputError("invalid or duplicate Stage 13 query labels")
        seen.add(ident)
        DocumentQueryService.validate_query(query)
        tier = item.get("summary_length")
        if (mode == "answer" and tier is not None or
                mode == "focused_summary" and tier not in ("short", "medium", "long")):
            raise BenchmarkInputError("invalid mode/length pairing in labels")
        expected_answer = item.get("expected_answer")
        expected_quotes = item.get("expected_quotes", [])
        excluded = item.get("excluded_quotes", [])
        if (not isinstance(expected_quotes, list)
                or not isinstance(excluded, list)
                or any(not isinstance(x, str) or not x for x in (*expected_quotes, *excluded))
                or any(x not in indexed[docid] for x in expected_quotes)):
            raise BenchmarkInputError("expected evidence quotes must be source-exact")
        if status == "not_found":
            if expected_answer is not None or expected_quotes:
                raise BenchmarkInputError("not_found must have no expected answer/evidence")
        elif status == "ambiguous":
            if expected_answer is not None or len(expected_quotes) < 2:
                raise BenchmarkInputError("ambiguity requires at least two source quotes")
        elif mode == "answer":
            if not isinstance(expected_answer, str) or expected_answer not in indexed[docid]:
                raise BenchmarkInputError("answer exact-match label must be in source")
        elif not expected_quotes:
            raise BenchmarkInputError("focused summaries need expected source quotes")
        if expected_answer is not None and (mode != "answer" or status != "found"):
            raise BenchmarkInputError("exact answer only applies to found answer cases")
    return indexed, cases


def _ratio(matches: int, count: int) -> float | None:
    return matches / count if count else None


def _grounded(result: Any, source: str) -> tuple[int, int, bool]:
    """Check exact source occurrence and parser-established TXT paragraph."""
    paragraphs = source.split("\n\n")
    supported = 0
    for item in result.evidence:
        loc = item.source_location
        para = loc.paragraph
        if (loc.document_type == "txt" and loc.page is None
                and type(para) is int and 1 <= para <= len(paragraphs)
                and item.text in source and item.text in paragraphs[para - 1]):
            supported += 1
    quoted_answer = (
        result.answer == "\n".join(item.text for item in result.evidence)
        if result.status == "found" else result.answer is None
    )
    return supported, len(result.evidence), quoted_answer


async def evaluate_async(
    fixture_path: Path = LABELS, *,
    stage9_dataset: Path = DATASET,
    stage11_labels: Path = STAGE11_LABELS,
) -> dict[str, Any]:
    sources, labels = _validate_labels(read_json(fixture_path))
    retriever = DocumentRetrievalService(DocumentExtractionService())
    service = DocumentQueryService(retriever)
    records = []
    latency_ms = []
    evidence_count = grounded_count = 0
    answer_matches = answer_count = 0
    no_answer_matches = no_answer_count = 0
    ambiguity_matches = ambiguity_count = 0
    focus_matches = focus_count = 0
    status_matches = 0

    tracing_here = not tracemalloc.is_tracing()
    if tracing_here:
        tracemalloc.start()
    try:
        for case in labels:
            started = time.perf_counter()
            result = await service.query_file_async(
                sources[case["document_id"]].encode("utf-8"),
                f'{case["document_id"]}.txt', case["query"],
                mode=case["mode"], summary_length=case.get("summary_length"),
            )
            elapsed = (time.perf_counter() - started) * 1000
            latency_ms.append(elapsed)
            supported, count, answer_grounded = _grounded(
                result, sources[case["document_id"]]
            )
            evidence_count += count
            grounded_count += supported
            correct_status = result.status == case["status"]
            status_matches += int(correct_status)
            all_source_grounded = supported == count and answer_grounded
            expected = case.get("expected_answer")
            exact_match = None
            no_answer_correct = None
            ambiguous_correct = None
            focused_correct = None
            quotes = case.get("expected_quotes", [])
            exclusions = case.get("excluded_quotes", [])
            if case["status"] == "found" and case["mode"] == "answer":
                answer_count += 1
                exact_match = bool(correct_status and all_source_grounded
                                   and result.answer == expected
                                   and all(x not in (result.answer or "") for x in exclusions))
                answer_matches += int(exact_match)
            elif case["status"] == "not_found":
                no_answer_count += 1
                no_answer_correct = bool(
                    correct_status and result.answer is None and not result.evidence
                )
                no_answer_matches += int(no_answer_correct)
            elif case["status"] == "ambiguous":
                ambiguity_count += 1
                excerpts = [item.text for item in result.evidence]
                ambiguous_correct = bool(
                    correct_status and all_source_grounded and result.answer is None
                    and len(excerpts) >= 2
                    and all(any(quote in text for text in excerpts) for quote in quotes)
                )
                ambiguity_matches += int(ambiguous_correct)
            elif case["mode"] == "focused_summary":
                focus_count += 1
                answer = result.answer or ""
                focused_correct = bool(
                    correct_status and all_source_grounded
                    and all(quote in answer for quote in quotes)
                    and all(quote not in answer for quote in exclusions)
                    and len(answer) <= DocumentQueryService._SUMMARY_BUDGETS[case["summary_length"]]
                )
                focus_matches += int(focused_correct)

            records.append({
                "id": case["id"],
                "expected_status": case["status"],
                "actual_status": result.status,
                "status_match": correct_status,
                "evidence_supported": supported,
                "evidence_count": count,
                "answer_source_grounded": answer_grounded,
                "answer_exact_match": exact_match,
                "no_answer_correct": no_answer_correct,
                "ambiguity_correct": ambiguous_correct,
                "focused_coverage": focused_correct,
                "latency_ms": round(elapsed, 3),
            })
        peak_bytes = tracemalloc.get_traced_memory()[1] if tracing_here else None
    finally:
        if tracing_here:
            tracemalloc.stop()

    # Evaluate only Stage 9 Development source cases through the existing
    # frozen Stage 11 retrieval harness; do not inspect Stage 9 holdout.
    retrieval = evaluate_retrieval(stage9_dataset, stage11_labels)
    ordered = sorted(latency_ms)
    percentile_95 = ordered[math.ceil(0.95 * len(ordered)) - 1]
    return {
        "version": 1,
        "split": "dev",
        "query_fixture_sha256": dataset_hash(fixture_path),
        "stage9_dev_dataset_sha256": retrieval["source_dataset_sha256"],
        "stage11_dev_labels_sha256": retrieval["retrieval_labels_sha256"],
        "stage11_recall_at_1": retrieval["recall_at_1"],
        "stage11_recall_at_3": retrieval["recall_at_3"],
        "stage11_queries": retrieval["evaluated_queries"],
        "stage12_queries": len(records),
        "status_accuracy": status_matches / len(records),
        "answer_exact_match": _ratio(answer_matches, answer_count),
        "answer_cases": answer_count,
        "evidence_support_rate": _ratio(grounded_count, evidence_count),
        "evidence_excerpts": evidence_count,
        "no_answer_accuracy": _ratio(no_answer_matches, no_answer_count),
        "no_answer_cases": no_answer_count,
        "ambiguous_detection": _ratio(ambiguity_matches, ambiguity_count),
        "ambiguous_cases": ambiguity_count,
        "focused_coverage": _ratio(focus_matches, focus_count),
        "focused_cases": focus_count,
        "median_latency_ms": round(statistics.median(latency_ms), 3),
        "p95_latency_ms_nearest_rank": round(percentile_95, 3),
        "peak_python_tracemalloc_bytes": peak_bytes,
        "peak_process_rss_bytes": "NOT_MEASURED",
        "stage10_frozen_semantic_quality_gate": "NOT_RETESTED",
        "production_semantic_quality_gate": "NOT_APPROVED",
        "records": records,
        "interpretation": (
            "Synthetic Development-only exact quotes and source-span checks, "
            "not human semantic entailment or statistically robust performance. "
            "Timing varies by hardware; tracemalloc excludes native/PyTorch allocations."
        ),
    }


def evaluate(
    fixture_path: Path = LABELS,
    stage9_dataset: Path = DATASET,
    stage11_labels: Path = STAGE11_LABELS,
) -> dict[str, Any]:
    return asyncio.run(evaluate_async(
        fixture_path, stage9_dataset=stage9_dataset, stage11_labels=stage11_labels
    ))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--labels", type=Path, default=LABELS)
    parser.add_argument("--stage9-dataset", type=Path, default=DATASET)
    parser.add_argument("--stage11-labels", type=Path, default=STAGE11_LABELS)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = evaluate(args.labels, args.stage9_dataset, args.stage11_labels)
        write_json(args.output, report)
    except (OSError, ValueError) as error:
        parser.exit(2, f"Stage 13 evaluation failed: {type(error).__name__}: {error}\n")
    print(
        f"Stage 13 Development: retrieval Recall@1={report['stage11_recall_at_1']:.3f}, "
        f"Recall@3={report['stage11_recall_at_3']:.3f}; "
        f"Answer EM={report['answer_exact_match']!s}, "
        f"No-answer={report['no_answer_accuracy']!s}, "
        f"Ambiguous={report['ambiguous_detection']!s}, "
        f"Focused={report['focused_coverage']!s}; "
        f"report: {args.output}; Production GO not evaluated"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
