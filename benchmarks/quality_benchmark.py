"""Offline-friendly, human-reviewed Persian summarization quality benchmark.

The benchmark is deliberately outside the ASGI dependency graph. Running it
never changes the service configuration or its HTTP endpoints.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import platform
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DATASET = Path(__file__).resolve().parent / "fixtures" / "quality_v1.json"
LENGTHS = ("short", "medium", "long")
SPLITS = ("dev", "holdout")
FACT_TYPES = {"date", "person", "number", "direction", "topic", "action"}
LABELS = {"covered", "omitted", "distorted"}
MAX_CASES = 1000
MAX_CASE_CHARS = 200_000


class BenchmarkInputError(ValueError):
    """The dataset, run file or review contains inconsistent labels."""


def read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise BenchmarkInputError("JSON root must be an object")
    return data


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Fail closed rather than overwriting an existing evaluation or user file.
    with path.open("x", encoding="utf-8", newline="\n") as out:
        json.dump(value, out, ensure_ascii=False, indent=2, sort_keys=True)
        out.write("\n")


def dataset_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_dataset(data: dict[str, Any]) -> list[dict[str, Any]]:
    if data.get("version") != 1 or data.get("license") != "CC0-1.0":
        raise BenchmarkInputError("dataset version/license is invalid")
    cases = data.get("cases")
    if not isinstance(cases, list) or not 1 <= len(cases) <= MAX_CASES:
        raise BenchmarkInputError("cases must be a bounded non-empty list")
    ids: set[str] = set()
    normalized = []
    for case in cases:
        if not isinstance(case, dict):
            raise BenchmarkInputError("each case must be an object")
        ident, text = case.get("id"), case.get("text")
        repeat = case.get("repeat", 1)
        if (not isinstance(ident, str) or not ident.isascii() or not ident
                or not all(ch.isalnum() or ch == "_" for ch in ident)
                or ident in ids):
            raise BenchmarkInputError("invalid or duplicate case id")
        ids.add(ident)
        if case.get("split") not in SPLITS:
            raise BenchmarkInputError(f"{ident}: invalid split")
        if (not isinstance(text, str) or not text.strip()
                or type(repeat) is not int or not 1 <= repeat <= 50
                or len(text) * repeat > MAX_CASE_CHARS):
            raise BenchmarkInputError(f"{ident}: invalid source text or repeat")
        expanded = text * repeat
        facts = case.get("facts")
        if not isinstance(facts, list) or not facts:
            raise BenchmarkInputError(f"{ident}: expected non-empty facts")
        fact_ids: set[str] = set()
        for fact in facts:
            if not isinstance(fact, dict):
                raise BenchmarkInputError(f"{ident}: invalid fact")
            fid, quote = fact.get("id"), fact.get("source_quote")
            if (not isinstance(fid, str) or not fid.isidentifier() or fid in fact_ids
                    or not isinstance(fact.get("type"), str) or fact["type"] not in FACT_TYPES
                    or not isinstance(quote, str)
                    or not quote.strip() or quote not in expanded):
                raise BenchmarkInputError(f"{ident}: invalid fact label or source quote")
            fact_ids.add(fid)
        reference = case.get("reference_summary")
        if not isinstance(reference, str) or not reference.strip():
            raise BenchmarkInputError(f"{ident}: missing human-authored reference summary")
        normalized.append({**case, "text": expanded, "facts": facts})
    if not {case["split"] for case in cases} == set(SPLITS):
        raise BenchmarkInputError("dataset must include both dev and holdout splits")
    return normalized


def runs_hash(runs: dict[str, Any]) -> str:
    encoded = json.dumps(runs, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def create_review_template(dataset: dict[str, Any], runs: dict[str, Any]) -> dict[str, Any]:
    cases = {c["id"]: c for c in validate_dataset(dataset)}
    if runs.get("dataset_sha256") is None or not isinstance(runs.get("results"), list):
        raise BenchmarkInputError("invalid runs file")
    reviews = []
    seen = set()
    for result in runs["results"]:
        if not isinstance(result, dict):
            raise BenchmarkInputError("invalid run result")
        key = (result.get("case_id"), result.get("summary_length"))
        if key in seen or key[0] not in cases or key[1] not in LENGTHS:
            raise BenchmarkInputError("duplicate or unknown run result")
        seen.add(key)
        if result.get("error_code"):
            continue
        if not isinstance(result.get("summary"), str):
            raise BenchmarkInputError("run result missing summary")
        reviews.append({
            "case_id": key[0], "summary_length": key[1],
            "facts": [{"id": f["id"], "label": None} for f in cases[key[0]]["facts"]],
            "claims": [],
        })
    return {"dataset_sha256": runs["dataset_sha256"], "runs_sha256": runs_hash(runs), "reviews": reviews,
            "instructions": "Set every fact label to covered/omitted/distorted. Split every "
                            "summary into atomic claims; assign supported boolean, "
                            "and exact source_quote evidence for supported claims."}


def score_reviews(dataset: dict[str, Any], runs: dict[str, Any], reviews: dict[str, Any],
                  *, expected_hash: str) -> dict[str, Any]:
    cases = {case["id"]: case for case in validate_dataset(dataset)}
    if (runs.get("dataset_sha256") != expected_hash
            or reviews.get("dataset_sha256") != expected_hash
            or reviews.get("runs_sha256") != runs_hash(runs)):
        raise BenchmarkInputError("dataset hash mismatch; do not score a changed dataset")
    run_items: dict[tuple[str, str], dict[str, Any]] = {}
    for item in runs.get("results", []):
        if not isinstance(item, dict):
            raise BenchmarkInputError("invalid run entry")
        key = (item.get("case_id"), item.get("summary_length"))
        if key in run_items or key[0] not in cases or key[1] not in LENGTHS:
            raise BenchmarkInputError("duplicate or unknown run entry")
        run_items[key] = item
    if not run_items:
        raise BenchmarkInputError("no run results")
    if not isinstance(reviews.get("reviews"), list):
        raise BenchmarkInputError("reviews must be a list")
    labels = Counter()
    claims = Counter()
    reviewed = set()
    for review in reviews["reviews"]:
        if not isinstance(review, dict):
            raise BenchmarkInputError("invalid review entry")
        key = (review.get("case_id"), review.get("summary_length"))
        if key in reviewed or key not in run_items or run_items[key].get("error_code"):
            raise BenchmarkInputError("review references duplicate, missing or failed run")
        reviewed.add(key)
        facts = review.get("facts")
        expected = {f["id"] for f in cases[key[0]]["facts"]}
        if not isinstance(facts, list) or {f.get("id") for f in facts if isinstance(f, dict)} != expected or len(facts) != len(expected):
            raise BenchmarkInputError("all facts must be reviewed exactly once")
        for fact in facts:
            if fact.get("label") not in LABELS:
                raise BenchmarkInputError("review contains unlabeled fact")
            labels[fact["label"]] += 1
            labels[f"type:{next(f['type'] for f in cases[key[0]]['facts'] if f['id'] == fact['id'])}:{fact['label']}"] += 1
        statements = review.get("claims")
        if not isinstance(statements, list) or (run_items[key].get("summary", "").strip() and not statements):
            raise BenchmarkInputError("nonempty summary requires manually reviewed atomic claims")
        for claim in statements:
            if (not isinstance(claim, dict) or not isinstance(claim.get("claim"), str)
                    or not claim["claim"].strip() or type(claim.get("supported")) is not bool):
                raise BenchmarkInputError("invalid reviewed claim")
            evidence = claim.get("evidence_quote")
            if claim["supported"]:
                if not isinstance(evidence, str) or not evidence.strip() or evidence not in cases[key[0]]["text"]:
                    raise BenchmarkInputError("supported claims need an exact source quotation")
            elif evidence not in (None, ""):
                raise BenchmarkInputError("unsupported claim must not cite supporting evidence")
            claims["supported" if claim["supported"] else "unsupported"] += 1
    fact_total = sum(labels[x] for x in LABELS)
    claim_total = claims["supported"] + claims["unsupported"]
    lengths: dict[str, dict[str, Any]] = {}
    for length in LENGTHS:
        items = [v for (cid, tier), v in run_items.items() if tier == length and not v.get("error_code")]
        lengths[length] = {"count": len(items),
                           "mean_output_chars": (sum(len(x.get("summary", "")) for x in items) / len(items)) if items else None}
    same_tiers = sorted({cid for (cid, _), _v in run_items.items()
                         if len({r.get("summary") for (name, _), r in run_items.items()
                                 if name == cid and not r.get("error_code")}) == 1
                         and sum(name == cid and not r.get("error_code") for (name, _), r in run_items.items()) > 1})
    return {
        "dataset_sha256": expected_hash,
        "runs": len(run_items), "successful_runs": sum(not r.get("error_code") for r in run_items.values()),
        "reviewed_runs": len(reviewed), "unreviewed_successful_runs": sum(not r.get("error_code") for k, r in run_items.items() if k not in reviewed),
        "fact_counts": {x: labels[x] for x in LABELS},
        "fact_coverage": labels["covered"] / fact_total if fact_total else None,
        "fact_distortion_rate": labels["distorted"] / fact_total if fact_total else None,
        "unsupported_claim_rate": claims["unsupported"] / claim_total if claim_total else None,
        "claims_reviewed": claim_total,
        "by_fact_type": {t: {s: labels[f"type:{t}:{s}"] for s in LABELS} for t in sorted(FACT_TYPES)},
        "length_diagnostics": lengths,
        "identical_output_across_tiers": same_tiers,
        "warning": "Metrics are human-annotated, not automated proof of semantic accuracy. "
                   "Partial reviews cannot be used as an overall quality baseline."
    }


async def execute_async(dataset_path: Path, output_path: Path, lengths: list[str], split: str) -> None:
    # Delayed imports: validate/score commands never import torch or download weights.
    from src.core.services.summarization.long_text_summarization_service import LongTextSummarizationService
    from src.infrastructure.di.bootstrap import bootstrap_di
    from src.infrastructure.di.inject import resolve
    from src.infrastructure.ml.mt5_model_provider import Mt5ModelProvider
    from src.infrastructure.utils.config_reader import ConfigReader

    dataset = read_json(dataset_path)
    selected = [c for c in validate_dataset(dataset) if split == "all" or c["split"] == split]
    bootstrap_di()
    service = resolve(LongTextSummarizationService)
    provider = resolve(Mt5ModelProvider)
    settings = ConfigReader().get("model")
    outputs = []
    for case in selected:
        for length in lengths:
            start = time.perf_counter()
            try:
                summary = await service.summarize_async(case["text"], length)
                count = await asyncio.to_thread(provider.count_input_tokens, summary)
                result = {"summary": summary, "output_tokens_including_specials": count}
            except Exception as error:
                # Retain the exception category, not input-dependent exception text.
                result = {"error_code": type(error).__name__}
            outputs.append({"case_id": case["id"], "summary_length": length,
                            "elapsed_seconds": round(time.perf_counter() - start, 3), **result})
    write_json(output_path, {
        "dataset_sha256": dataset_hash(dataset_path), "dataset_version": dataset["version"],
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "python": platform.python_version(), "platform": platform.platform(),
        "model_settings": {key: settings[key] for key in (
            "id", "revision", "device", "max_input_tokens", "max_input_characters",
            "max_output_tokens", "num_beams", "repetition_penalty", "length_penalty",
            "early_stopping", "max_concurrent_inferences", "queue_wait_seconds"
        ) if key in settings}, "split": split,
        "results": outputs,
        "limitations": "No human fact review performed; summary shape and token counts do not prove factual accuracy. Peak RAM not measured."
    })


def extraction_diagnostic(file: Path, anchors: Path, output: Path) -> None:
    from src.core.services.summarization.document_extraction_service import DocumentExtractionService
    from src.infrastructure.di.bootstrap import bootstrap_di
    from src.infrastructure.di.inject import resolve

    if file.stat().st_size > DocumentExtractionService.MAX_INPUT_BYTES:
        raise BenchmarkInputError("document exceeds extractor input budget")
    checks = [x.strip() for x in anchors.read_text(encoding="utf-8").splitlines() if x.strip()]
    if not checks or len(checks) > 1000:
        raise BenchmarkInputError("anchors must contain 1-1000 non-empty lines")
    bootstrap_di()
    extracted = resolve(DocumentExtractionService).extract(file.read_bytes(), file.name)
    matched = sum(phrase in extracted for phrase in checks)
    write_json(output, {
        "file_extension": file.suffix.lower(), "anchors_total": len(checks),
        "anchors_found_exactly": matched, "exact_anchor_recall": matched / len(checks),
        "extracted_characters": len(extracted),
        "warning": "Exact anchor recall diagnoses extraction/RTL, not model summarization; punctuation and whitespace matter."
    })


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DATASET)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate")
    run = sub.add_parser("run")
    run.add_argument("--output", type=Path, required=True)
    run.add_argument("--split", choices=(*SPLITS, "all"), default="dev")
    run.add_argument("--lengths", nargs="+", choices=LENGTHS, default=list(LENGTHS))
    review = sub.add_parser("review-template")
    review.add_argument("--runs", type=Path, required=True)
    review.add_argument("--output", type=Path, required=True)
    score = sub.add_parser("score")
    score.add_argument("--runs", type=Path, required=True)
    score.add_argument("--reviews", type=Path, required=True)
    score.add_argument("--output", type=Path, required=True)
    extraction = sub.add_parser("inspect-extraction")
    extraction.add_argument("--file", type=Path, required=True)
    extraction.add_argument("--anchors", type=Path, required=True)
    extraction.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        data = read_json(args.dataset) if args.command != "inspect-extraction" else None
        if args.command == "validate":
            cases = validate_dataset(data)
            print(f"VALID: {len(cases)} cases; splits: {dict(Counter(c['split'] for c in cases))}; sha256={dataset_hash(args.dataset)}")
        elif args.command == "run":
            asyncio.run(execute_async(args.dataset, args.output, list(dict.fromkeys(args.lengths)), args.split))
            print(f"Saved raw model outputs: {args.output}")
        elif args.command == "review-template":
            runs = read_json(args.runs)
            if runs.get("dataset_sha256") != dataset_hash(args.dataset):
                raise BenchmarkInputError("dataset hash mismatch")
            write_json(args.output, create_review_template(data, runs))
            print(f"Saved unreviewed template: {args.output}")
        elif args.command == "score":
            result = score_reviews(data, read_json(args.runs), read_json(args.reviews), expected_hash=dataset_hash(args.dataset))
            write_json(args.output, result)
            print(f"Saved reviewed metrics: {args.output}; reviewed={result['reviewed_runs']} unreviewed={result['unreviewed_successful_runs']}")
        else:
            extraction_diagnostic(args.file, args.anchors, args.output)
            print(f"Saved extraction diagnostics: {args.output}")
    except (OSError, ValueError, json.JSONDecodeError) as error:
        parser.exit(2, f"Benchmark input or execution failed: {type(error).__name__}: {error}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
