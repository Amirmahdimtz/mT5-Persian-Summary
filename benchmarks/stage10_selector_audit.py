"""Audit lexical evidence selection with no model generation or document export.

This Stage 10 development-only tool tests whether original-source statements
can enter the current extractive Map selector. It does not reproduce actual
Map-generation outputs or establish semantic accuracy.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path
from typing import Any

from benchmarks.quality_benchmark import (
    BenchmarkInputError, dataset_hash, read_json, runs_hash, write_json,
)
from benchmarks.stage10_trace import select_dev_case


def lead_prose_candidates(source: str) -> list[str]:
    """Preview source sentences in the preface and first major Markdown section.

    This *diagnostic only* deliberately never changes what the API or Map
    selects. Introductory prose commonly carries the document's scope; the
    caller must still evaluate section context, importance and token limits.
    """
    heading = re.compile(r"^(#{1,6})[ \t]+(.+)$")
    sentence_gap = re.compile(r"(?<=[.!?؟؛])[ \t]+")
    candidates: list[str] = []
    seen_major = False
    fenced = False
    for raw in source.splitlines():
        line = raw.strip()
        if line.startswith("```"):
            fenced = not fenced
            continue
        if fenced or not line or line == "---":
            continue
        match = heading.match(line)
        if match:
            if len(match.group(1)) == 2:
                if seen_major:
                    break
                seen_major = True
            continue
        if line.startswith(("-", "*", "•", "|")) or line.startswith("~~~"):
            continue
        # Preserve the actual quote verbatim; strip only Markdown quotation
        # prefix used by metadata. No benchmark fact IDs guide selection.
        if line.startswith(">"):
            line = line.lstrip(">").strip()
        if not line or line.startswith("#"):
            continue
        for fragment in sentence_gap.split(line):
            candidate = fragment.strip()
            if 24 <= len(candidate) <= 300 and re.search(r"[\w\u0600-\u06ff]", candidate):
                if candidate not in candidates:
                    candidates.append(candidate)
        if len(candidates) >= 32:
            break
    return candidates[:32]


def audit_case(case: dict[str, Any], final_text: str, chunks: list[str],
               selector: Any, excluded: set[str],
               lead_prose: list[str] | None = None) -> dict[str, Any]:
    """Report exact-match fact eligibility, never excerpts or generated text."""
    selected = [line for chunk in chunks for line in selector(chunk)]
    eligible = list(dict.fromkeys(line for line in selected if line not in excluded))
    facts = []
    for fact in case["facts"]:
        quote = fact["source_quote"]
        row = {
            "fact_id": fact["id"],
            "found_in_original_source": quote in case["text"],
            "found_in_selected_clauses": any(quote in line for line in selected),
            "found_in_eligible_clauses": any(quote in line for line in eligible),
            "found_in_final_output_verbatim": quote in final_text,
            "found_in_excluded_clauses": any(quote in line for line in excluded),
        }
        if lead_prose is not None:
            row["found_in_lead_prose_preview"] = any(quote in line for line in lead_prose)
        facts.append(row)
    result = {
        "case_id": case["id"],
        "chunk_count": len(chunks),
        "selected_clause_count": len(selected),
        "eligible_unique_clause_count": len(eligible),
        "excluded_source_clause_count": len(excluded),
        "facts": facts,
    }
    if lead_prose is not None:
        result["lead_prose_candidate_count"] = len(lead_prose)
    return result


async def execute_async(
    dataset_path: Path, runs_path: Path, output: Path,
    *, preview_lead_prose: bool = False,
) -> None:
    if type(preview_lead_prose) is not bool:
        raise BenchmarkInputError("preview_lead_prose must be boolean")
    if output.exists():
        raise BenchmarkInputError("output already exists; choose a new versioned name")
    dataset = read_json(dataset_path)
    run = read_json(runs_path)
    if not isinstance(run, dict):
        raise BenchmarkInputError("run must be an object")
    digest = dataset_hash(dataset_path)
    if run.get("dataset_sha256") != digest:
        raise BenchmarkInputError("run dataset hash must match source data")
    pipeline = run.get("pipeline_settings")
    if not isinstance(pipeline, dict) or pipeline.get("preserve_map_evidence") is not True or pipeline.get("source_grounded_final") is not True:
        raise BenchmarkInputError("audit requires the source-grounded development candidate")
    if run.get("split") != "dev":
        raise BenchmarkInputError("audit is restricted to development runs")
    results = run.get("results")
    if not isinstance(results, list) or not results:
        raise BenchmarkInputError("run results must be a nonempty list")

    # Validate all run records before importing tokenizer/model dependencies.
    selected = []
    seen: set[str] = set()
    for entry in results:
        if not isinstance(entry, dict):
            raise BenchmarkInputError("invalid run result")
        case_id = entry.get("case_id")
        if not isinstance(case_id, str) or case_id in seen:
            raise BenchmarkInputError("duplicate or invalid run case id")
        seen.add(case_id)
        case = select_dev_case(dataset, case_id)
        if entry.get("summary_length") != "medium":
            raise BenchmarkInputError("use the fixed medium development tier")
        summary = entry.get("summary")
        if entry.get("error_code") or not isinstance(summary, str) or not summary.strip():
            raise BenchmarkInputError("audit requires successful nonempty summaries")
        selected.append((case, summary))

    # Same DI-resolved tokenizer/chunker and selection logic as the real service;
    # no summarize_async or model.generate call is ever made.
    from src.core.services.summarization.long_text_summarization_service import LongTextSummarizationService
    from src.infrastructure.di.bootstrap import bootstrap_di
    from src.infrastructure.di.inject import resolve
    from src.infrastructure.ml.mt5_model_provider import Mt5ModelProvider
    from src.infrastructure.utils.config_reader import ConfigReader

    bootstrap_di()
    service = resolve(LongTextSummarizationService)
    provider = resolve(Mt5ModelProvider)
    if service._provider is not provider:
        raise BenchmarkInputError("diagnostic must share the actual DI provider")
    settings = ConfigReader().get("model")
    model_settings = run.get("model_settings")
    if (not isinstance(model_settings, dict) or
            model_settings.get("revision") != settings.get("revision") or
            model_settings.get("no_repeat_ngram_size", 0) != settings.get("no_repeat_ngram_size", 0)):
        raise BenchmarkInputError("the checkpoint and decoding configuration must match the run")

    audits = []
    for case, summary in selected:
        source = await asyncio.to_thread(service._chunker.normalize, case["text"])
        chunks = await asyncio.to_thread(service._chunker.chunk, source)
        excluded = service._excluded_original_clauses(source)
        prose = lead_prose_candidates(source) if preview_lead_prose else None
        audits.append(audit_case(
            case, summary, chunks, service._evidence_lines, excluded,
            lead_prose=prose,
        ))
    write_json(output, {
        "stage": "stage10_offline_selector_audit",
        "preview_lead_prose": preview_lead_prose,
        "dataset_sha256": digest,
        "runs_sha256": runs_hash(run),
        "inference_calls": 0,
        "semantic_review_status": "NOT_REVIEWED",
        "results": audits,
        "limitations": (
            "Exact source-quote presence is lexical, not semantic coverage. "
            "The audit examines candidate clauses before model inference and before "
            "intermediate token-cap insertion; it does not prove which clauses "
            "were present in real Map outputs. No raw source or generated text is exported."
        ),
    })


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--runs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--preview-lead-prose", action="store_true",
        help="Audit introductory prose eligibility without changing inference or service behavior",
    )
    args = parser.parse_args(argv)
    try:
        asyncio.run(execute_async(
            args.dataset, args.runs, args.output,
            preview_lead_prose=args.preview_lead_prose,
        ))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.exit(2, f"Stage 10 selector audit failed: {type(exc).__name__}: {exc}\n")
    print(f"Saved inference-free development selector audit: {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
