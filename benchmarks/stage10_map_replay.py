"""Replay first-Map source-excerpt selection without running model inference.

This is an offline, development-only Stage 10 diagnostic. It recomputes
actual tokenizer budgets for a previously captured first-map output and
writes only counters/fact IDs, never source or generated text. No checkpoint
weights, generation, HTTP endpoint or production state is modified.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from benchmarks.quality_benchmark import BenchmarkInputError, dataset_hash, read_json, write_json
from benchmarks.stage10_trace import select_dev_case


def _validate_probe(probe: dict[str, Any], *, case_id: str, digest: str) -> str:
    if probe.get("dataset_sha256") != digest or probe.get("case_id") != case_id:
        raise BenchmarkInputError("first-map probe dataset or case does not match")
    if probe.get("stage") != "first_map_only" or probe.get("split") != "dev":
        raise BenchmarkInputError("first-map probe must be a development first-map result")
    summary = probe.get("first_map_generated_text")
    if not isinstance(summary, str) or not summary.strip():
        raise BenchmarkInputError("first-map result must contain generated text")
    if type(probe.get("first_chunk_characters")) is not int or probe["first_chunk_characters"] < 1:
        raise BenchmarkInputError("invalid first chunk size")
    if type(probe.get("chunk_count")) is not int or probe["chunk_count"] < 2:
        raise BenchmarkInputError("invalid chunk count")
    if type(probe.get("max_output_tokens")) is not int or probe["max_output_tokens"] < 1:
        raise BenchmarkInputError("invalid original map token ceiling")
    if not isinstance(probe.get("model_revision"), str):
        raise BenchmarkInputError("missing model revision")
    if type(probe.get("no_repeat_ngram_size")) is not int:
        raise BenchmarkInputError("invalid decoder configuration")
    return summary.strip()


async def execute_async(dataset: Path, first_map: Path, output: Path) -> None:
    """Replay original Map excerpt selection, no call to summarize_async."""
    # Check the local output path before expensive tokenizer initialization.
    if output.exists():
        raise BenchmarkInputError("output already exists; choose a new filename")
    probe = read_json(first_map)
    if not isinstance(probe, dict):
        raise BenchmarkInputError("first-map probe must be an object")
    case_id = probe.get("case_id")
    if not isinstance(case_id, str):
        raise BenchmarkInputError("missing case ID")
    case = select_dev_case(read_json(dataset), case_id)
    source_sha = dataset_hash(dataset)
    summary = _validate_probe(probe, case_id=case_id, digest=source_sha)

    # Lazy imports: test and validation do not download model weights.
    from src.core.services.summarization.long_text_summarization_service import LongTextSummarizationService
    from src.infrastructure.di.bootstrap import bootstrap_di
    from src.infrastructure.di.inject import resolve
    from src.infrastructure.ml.mt5_model_provider import Mt5ModelProvider
    from src.infrastructure.utils.config_reader import ConfigReader

    bootstrap_di()
    service = resolve(LongTextSummarizationService)
    provider = resolve(Mt5ModelProvider)
    if service._provider is not provider:
        raise BenchmarkInputError("diagnostic and summarizer must share DI provider")
    settings = ConfigReader().get("model")
    if (
        settings.get("revision") != probe["model_revision"]
        or settings.get("no_repeat_ngram_size", 0) != probe["no_repeat_ngram_size"]
        or provider.max_output_tokens != probe["max_output_tokens"]
    ):
        raise BenchmarkInputError("replay requires the original checkpoint and generation configuration")
    source = await asyncio.to_thread(service._chunker.normalize, case["text"])
    chunks = await asyncio.to_thread(service._chunker.chunk, source)
    if len(chunks) != probe["chunk_count"] or len(chunks[0]) != probe["first_chunk_characters"]:
        raise BenchmarkInputError("first chunk does not match original Map probe")
    first = chunks[0]
    quotes = {fact["id"]: fact["source_quote"] for fact in case["facts"]}
    selected = service._evidence_lines(first)
    replayed = await service._augment_map_async(first, summary)

    selected_new = [line for line in selected if line not in summary]
    appended = [line for line in selected_new if line in replayed]
    result = {
        "stage": "first_map_evidence_replay",
        "case_id": case_id,
        "dataset_sha256": source_sha,
        "model_revision": probe["model_revision"],
        "max_output_tokens": provider.max_output_tokens,
        "original_map_tokens_including_specials": await asyncio.to_thread(provider.count_input_tokens, summary),
        "replayed_map_tokens_including_specials": await asyncio.to_thread(provider.count_input_tokens, replayed),
        "selected_source_lines": len(selected),
        "new_source_lines_eligible": len(selected_new),
        "appended_source_lines": len(appended),
        "output_changed_by_preservation": replayed != summary,
        "source_fact_ids_in_first_map_input": [key for key, quote in quotes.items() if quote in first],
        "fact_ids_in_selected_source_lines": [key for key, quote in quotes.items() if any(quote in line for line in selected)],
        "fact_ids_in_replayed_map_output": [key for key, quote in quotes.items() if quote in replayed],
        "inference_calls": 0,
        "semantic_review_status": "NOT_REVIEWED",
        "limitations": (
            "Offline replay uses the previously saved first-Map generation and the current "
            "extractive code; it does not prove what v2 actually generated at Map or Reduce. "
            "Quote matching is lexical, not a semantic evaluation. No source or generated text is stored."
        ),
    }
    write_json(output, result)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--first-map", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        asyncio.run(execute_async(args.dataset, args.first_map, args.output))
    except (OSError, ValueError, json.JSONDecodeError) as error:
        parser.exit(2, f"Stage 10 offline Map replay failed: {type(error).__name__}: {error}\n")
    print(f"Saved inference-free first-Map evidence replay: {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
