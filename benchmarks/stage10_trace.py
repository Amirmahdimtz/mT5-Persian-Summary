"""Local-only Stage 10 model-call trace with no document or summary text saved.

The trace measures literal evidence-quote survival, not semantic fact coverage.
An unchanged local development case is required; holdout inputs are rejected.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any, Awaitable, Callable

from benchmarks.quality_benchmark import (
    BenchmarkInputError,
    dataset_hash,
    duplicate_fourgram_fraction,
    read_json,
    validate_dataset,
    write_json,
)


class MapEvidenceRecorder:
    """Observe the *post-generation* Map augmentation without saving text.

    CallRecorder sees provider.generate outputs, which precede this stage.
    These events expose whether source excerpts survived the tokenizer cap
    and whether they reached the following model call. Phrase matching is
    literal and must never be reported as semantic fact coverage.
    """

    MAX_EVENTS = 128

    def __init__(
        self, facts: list[dict[str, str]], model_calls: list[dict[str, Any]],
        selector: Callable[[str], list[str]],
    ) -> None:
        self._quotes = {fact["id"]: fact["source_quote"] for fact in facts}
        self._model_calls = model_calls
        self._selector = selector
        self.events: list[dict[str, Any]] = []

    def _matches(self, text: str) -> list[str]:
        return [key for key, quote in self._quotes.items() if quote in text]

    def wrap(self, method: Callable[[str, str], Awaitable[str]]) -> Callable[[str, str], Awaitable[str]]:
        async def measured(source: str, summary: str) -> str:
            if len(self.events) >= self.MAX_EVENTS:
                raise BenchmarkInputError("Map augmentation event budget exhausted")
            selected = self._selector(source)
            entry: dict[str, Any] = {
                "event": len(self.events) + 1,
                "preceding_model_call": len(self._model_calls),
                "source_chars": len(source),
                "before_chars": len(summary),
                "source_exact_fact_ids": self._matches(source),
                "before_exact_fact_ids": self._matches(summary),
                "selected_source_lines": len(selected),
                "selected_exact_fact_ids": [
                    key for key, quote in self._quotes.items()
                    if any(quote in line for line in selected)
                ],
            }
            try:
                augmented = await method(source, summary)
            except BaseException as error:
                entry["error_code"] = type(error).__name__
                raise
            else:
                entry.update({
                    "after_chars": len(augmented),
                    "after_exact_fact_ids": self._matches(augmented),
                    "appended_source_lines": sum(
                        line not in summary and line in augmented for line in selected
                    ),
                })
                return augmented
            finally:
                self.events.append(entry)
        return measured


class CallRecorder:
    """Capture safe bounded inference metadata, never private input or output text."""

    def __init__(self, source: str, facts: list[dict[str, str]]) -> None:
        self._source = source
        self._quotes = {fact["id"]: fact["source_quote"] for fact in facts}
        self.calls: list[dict[str, Any]] = []

    def wrap(self, method: Callable[..., Awaitable[str]]) -> Callable[..., Awaitable[str]]:
        async def measured(text: str, *, max_output_tokens: int | None = None) -> str:
            if len(self.calls) >= 128:
                raise BenchmarkInputError("trace call budget exceeded")
            entry: dict[str, Any] = {
                "call": len(self.calls) + 1,
                "input_chars": len(text),
                "max_output_tokens": max_output_tokens,
                "input_is_original_source_span": text.strip() in self._source,
                "input_contains_exact_fact_quotes": [
                    key for key, quote in self._quotes.items() if quote in text
                ],
            }
            start = time.perf_counter()
            try:
                result = await method(text, max_output_tokens=max_output_tokens)
            except BaseException as error:
                entry["error_code"] = type(error).__name__
                raise
            else:
                entry.update({
                    "output_chars": len(result),
                    "output_repeated_fourgram_fraction": duplicate_fourgram_fraction(result),
                    "output_contains_exact_fact_quotes": [
                        key for key, quote in self._quotes.items() if quote in result
                    ],
                })
                return result
            finally:
                entry["elapsed_seconds"] = round(time.perf_counter() - start, 3)
                self.calls.append(entry)
        return measured


def select_dev_case(data: dict[str, Any], case_id: str) -> dict[str, Any]:
    matches = [item for item in validate_dataset(data) if item["id"] == case_id]
    if len(matches) != 1:
        raise BenchmarkInputError("case-id not found in dataset")
    case = matches[0]
    if case["split"] != "dev":
        raise BenchmarkInputError("trace may only inspect development cases, not holdout")
    return case


async def execute_async(
    dataset_path: Path, case_id: str, length: str, output: Path,
    *, preserve_map_evidence: bool = False,
) -> None:
    # Delayed imports prevent model downloads during offline unit tests.
    from src.core.services.summarization.long_text_summarization_service import LongTextSummarizationService
    from src.infrastructure.di.bootstrap import bootstrap_di
    from src.infrastructure.di.inject import resolve
    from src.infrastructure.ml.mt5_model_provider import Mt5ModelProvider
    from src.infrastructure.utils.config_reader import ConfigReader

    if length not in ("short", "medium", "long"):
        raise BenchmarkInputError("invalid summary length")
    if type(preserve_map_evidence) is not bool:
        raise BenchmarkInputError("preserve_map_evidence must be a boolean")
    if output.exists():
        raise BenchmarkInputError("trace output already exists; choose a new versioned path")
    case = select_dev_case(read_json(dataset_path), case_id)
    bootstrap_di()
    service = resolve(LongTextSummarizationService)
    provider = resolve(Mt5ModelProvider)
    if service._provider is not provider:
        raise BenchmarkInputError("service and trace must share the same DI provider")
    normalized_source = service._chunker.normalize(case["text"])
    recorder = CallRecorder(normalized_source, case["facts"])
    original = provider.summarize_async
    map_recorder: MapEvidenceRecorder | None = None
    original_map: Callable[[str, str], Awaitable[str]] | None = None
    if preserve_map_evidence:
        original_map = service._augment_map_async
        map_recorder = MapEvidenceRecorder(
            case["facts"], recorder.calls, service._evidence_lines
        )
    provider.summarize_async = recorder.wrap(original)
    if map_recorder is not None and original_map is not None:
        service._augment_map_async = map_recorder.wrap(original_map)
    start = time.perf_counter()
    summary: str | None = None
    failure: str | None = None
    try:
        try:
            if preserve_map_evidence:
                summary = await service.summarize_async(
                    case["text"], length, preserve_map_evidence=True
                )
            else:
                summary = await service.summarize_async(case["text"], length)
        except Exception as error:
            failure = type(error).__name__
    finally:
        provider.summarize_async = original
        if original_map is not None:
            service._augment_map_async = original_map
    settings = ConfigReader().get("model")
    report = {
        "dataset_sha256": dataset_hash(dataset_path),
        "case_id": case_id,
        "summary_length": length,
        "model_revision": settings["revision"],
        "no_repeat_ngram_size": settings.get("no_repeat_ngram_size", 0),
        "pipeline_settings": {"preserve_map_evidence": preserve_map_evidence},
        "map_evidence_augmentations": (
            map_recorder.events if map_recorder is not None else []
        ),
        "source_characters": len(normalized_source),
        "expected_fact_ids": [f["id"] for f in case["facts"]],
        "calls": recorder.calls,
        "successful": summary is not None,
        "error_code": failure,
        "final_output_characters": len(summary) if summary is not None else None,
        "final_repeated_fourgram_fraction": (
            duplicate_fourgram_fraction(summary) if summary is not None else None
        ),
        "total_elapsed_seconds": round(time.perf_counter() - start, 3),
        "warning": (
            "Exact text matches do not prove semantic fact survival or omission. "
            "Post-Map metadata describes actual augmentation when enabled, not just "
            "raw model output. No source or generated text is saved; do not infer a specific model root cause "
            "without reviewing intermediate summaries. This CLI runs only in a local process."
        ),
    }
    write_json(output, report)
    if failure is not None:
        raise BenchmarkInputError("trace recorded an inference failure; see error_code")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--length", choices=("short", "medium", "long"), default="medium")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--preserve-map-evidence", action="store_true",
        help="Trace the Stage 10 development-only post-generation Map evidence trial",
    )
    args = parser.parse_args(argv)
    try:
        asyncio.run(execute_async(
            args.dataset, args.case_id, args.length, args.output,
            preserve_map_evidence=args.preserve_map_evidence,
        ))
    except (OSError, ValueError, json.JSONDecodeError) as error:
        parser.exit(2, f"Stage 10 trace failed: {type(error).__name__}: {error}\n")
    print(f"Saved privacy-minimized development inference trace: {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
