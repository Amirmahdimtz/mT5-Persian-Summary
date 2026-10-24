"""Bounded, sequential and ASGI-safe hierarchical Persian summarization."""

from __future__ import annotations

import asyncio

from src.core.services.summarization.text_chunking_service import (
    ChunkingInputError,
    ChunkingLimitError,
    TextChunkingService,
)
from src.infrastructure.di.inject import inject
from src.infrastructure.ml.mt5_model_provider import ModelOutputError, Mt5ModelProvider


class SummarizationInputError(ValueError):
    """The summary length or source text is invalid."""


class SummarizationLimitError(RuntimeError):
    """Hierarchy depth or model call budget is exhausted."""


class SummarizationNoProgressError(RuntimeError):
    """The hierarchy does not compress enough to complete safely."""


class SummaryOutputLimitError(ModelOutputError):
    """Final text exceeds the requested encoded-token output budget."""


@inject
class LongTextSummarizationService:
    """Map all chunks, recursively reduce them, then summarize once more.

    Model calls are sequential; Mt5ModelProvider separately serializes calls
    across concurrent service instances. Tokenization/chunking run in worker
    threads, leaving the event loop responsive. No partial result is returned
    on limits, cancellation, or a failed intermediate model call.
    """

    MAX_HIERARCHY_LEVELS = 6
    MAX_MODEL_CALLS = 128
    _LENGTH_FRACTIONS = {"short": (1, 3), "medium": (2, 3), "long": (3, 3)}

    def __init__(
        self, text_chunking_service: TextChunkingService, model_provider: Mt5ModelProvider
    ) -> None:
        self._chunker = text_chunking_service
        self._provider = model_provider

    def output_token_budget(self, summary_length: str) -> int:
        if not isinstance(summary_length, str) or summary_length not in self._LENGTH_FRACTIONS:
            raise SummarizationInputError("summary_length must be short, medium or long")
        numerator, denominator = self._LENGTH_FRACTIONS[summary_length]
        return (self._provider.max_output_tokens * numerator + denominator - 1) // denominator

    async def summarize_async(self, text: str, summary_length: str = "medium") -> str:
        desired_budget = self.output_token_budget(summary_length)
        try:
            current = self._chunker.normalize(text)
        except ChunkingInputError as error:
            raise SummarizationInputError("text must contain valid nonempty content") from error
        if len(current) > self._chunker.MAX_TEXT_CHARACTERS:
            # The same documented work budget applies to short and long paths.
            raise ChunkingLimitError("input exceeds chunking character budget")

        calls = 0

        async def infer(value: str, limit: int) -> str:
            nonlocal calls
            if calls >= self.MAX_MODEL_CALLS:
                raise SummarizationLimitError("model call budget exhausted")
            if not await asyncio.to_thread(self._chunker.fits, value):
                raise SummarizationLimitError("hierarchy input exceeds provider budget")
            calls += 1
            summary = await self._provider.summarize_async(value, max_output_tokens=limit)
            if not isinstance(summary, str) or not summary.strip():
                raise ModelOutputError("mT5 returned an empty hierarchical summary")
            return summary.strip()

        for _ in range(self.MAX_HIERARCHY_LEVELS):
            if await asyncio.to_thread(self._chunker.fits, current):
                result = await infer(current, desired_budget)
                # Re-encoding is not always token-identical to decoder IDs;
                # fail rather than silently trimming or claiming a false cap.
                if (len(result) > self._provider.max_input_characters or
                        not await asyncio.to_thread(self._output_fits, result, desired_budget)):
                    raise SummaryOutputLimitError("summary exceeds requested token budget")
                return result

            chunks = await asyncio.to_thread(self._chunker.chunk, current)
            if len(chunks) <= 1:
                raise SummarizationNoProgressError("chunker cannot reduce long input")
            if calls + len(chunks) + 1 > self.MAX_MODEL_CALLS:
                raise SummarizationLimitError("model call budget exhausted")

            parts: list[str] = []
            for chunk in chunks:
                # Intermediate summaries get full configured output budget;
                # the requested final length applies only to the final pass.
                parts.append(await infer(chunk, self._provider.max_output_tokens))
            merged = "\n\n".join(parts)
            # A very small reduction cannot converge within bounded depth.
            if len(merged) * 100 >= len(current) * 95:
                raise SummarizationNoProgressError("hierarchy failed to reduce text sufficiently")
            if len(merged) > self._chunker.MAX_TEXT_CHARACTERS:
                raise SummarizationLimitError("intermediate summaries exceed work budget")
            current = merged

        raise SummarizationLimitError("maximum hierarchy depth reached")

    def _output_fits(self, output: str, budget: int) -> bool:
        return self._provider.count_input_tokens(output) <= budget
