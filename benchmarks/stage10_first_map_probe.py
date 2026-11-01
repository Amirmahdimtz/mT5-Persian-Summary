"""Opt-in local probe for one long-document first-map summary.

Unlike the privacy-minimized stage10_trace, this diagnostic intentionally
includes generated text. It never saves original input chunks and refuses
holdout examples. Never commit or upload the output without reviewing it.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any

from benchmarks.quality_benchmark import (
    BenchmarkInputError,
    dataset_hash,
    duplicate_fourgram_fraction,
    read_json,
    write_json,
)
from benchmarks.stage10_trace import select_dev_case


async def execute_async(dataset_path: Path, case_id: str, output: Path) -> None:
    """Generate the first map summary only (one real mT5 call, not eleven)."""
    # Import heavy components only when the command is actually run.
    from src.core.services.summarization.long_text_summarization_service import LongTextSummarizationService
    from src.infrastructure.di.bootstrap import bootstrap_di
    from src.infrastructure.di.inject import resolve
    from src.infrastructure.ml.mt5_model_provider import Mt5ModelProvider
    from src.infrastructure.utils.config_reader import ConfigReader

    if output.exists():
        raise BenchmarkInputError("output already exists; choose a new local versioned path")
    case = select_dev_case(read_json(dataset_path), case_id)
    bootstrap_di()
    service = resolve(LongTextSummarizationService)
    provider = resolve(Mt5ModelProvider)
    if service._provider is not provider:
        raise BenchmarkInputError("service and provider must share the same DI instance")

    source = await asyncio.to_thread(service._chunker.normalize, case["text"])
    chunks = await asyncio.to_thread(service._chunker.chunk, source)
    if len(chunks) < 2:
        raise BenchmarkInputError("case does not need a map/reduce hierarchy")
    first = chunks[0]
    ceiling = provider.max_output_tokens
    start = time.perf_counter()
    # Match the exact map call in LongTextSummarizationService.
    summary = await provider.summarize_async(first, max_output_tokens=ceiling)
    if not isinstance(summary, str) or not summary.strip():
        raise BenchmarkInputError("model returned an empty first-map summary")
    summary = summary.strip()
    output_tokens = await asyncio.to_thread(provider.count_input_tokens, summary)
    settings = ConfigReader().get("model")
    report: dict[str, Any] = {
        "dataset_sha256": dataset_hash(dataset_path),
        "case_id": case_id,
        "split": "dev",
        "stage": "first_map_only",
        "model_revision": settings["revision"],
        "no_repeat_ngram_size": settings.get("no_repeat_ngram_size", 0),
        "first_chunk_characters": len(first),
        "chunk_count": len(chunks),
        "input_fact_ids": [f["id"] for f in case["facts"] if f["source_quote"] in first],
        "output_exact_quote_fact_ids": [
            f["id"] for f in case["facts"] if f["source_quote"] in summary
        ],
        "max_output_tokens": ceiling,
        "output_tokens_including_specials": output_tokens,
        "output_characters": len(summary),
        "output_repeated_fourgram_fraction": duplicate_fourgram_fraction(summary),
        "elapsed_seconds": round(time.perf_counter() - start, 3),
        "first_map_generated_text": summary,
        "warning": (
            "Contains generated text that may quote private source content; keep local "
            "and do not commit. Exact quote matches are not semantic assessment. "
            "This diagnostic does not change the summarization API or checkpoint."
        ),
    }
    write_json(output, report)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--allow-generated-text", action="store_true",
        help="Explicitly consent to storing generated text in a local JSON file",
    )
    args = parser.parse_args(argv)
    if not args.allow_generated_text:
        parser.exit(2, "First-map probe requires --allow-generated-text acknowledgement\n")
    try:
        asyncio.run(execute_async(args.dataset, args.case_id, args.output))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.exit(2, f"First-map probe failed: {type(exc).__name__}: {exc}\n")
    print(f"Saved local first-map generated-text probe: {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
