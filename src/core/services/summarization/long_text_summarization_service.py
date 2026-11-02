"""Bounded, sequential and ASGI-safe hierarchical Persian summarization."""

from __future__ import annotations

import asyncio
import re

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
    _MAP_EVIDENCE_LINES = 3
    _BULLET = re.compile(r"^[-*•][ \t]+(.+)$")
    _FIRST_SENTENCE = re.compile(r"(?<=[.!?؟؛])[ \t]+")
    # Generic Persian obligation/decision signals, not benchmark fact IDs.
    _OBLIGATION = re.compile(r"باید|نباید|الزام|ممنوع|ضروری|موظف")
    _ACTION = re.compile(r"نساز|نکن|تصمیم")
    _CODE = re.compile(r"[@`]")
    _DETAIL = re.compile(r"[/\d۰-۹A-Z]")
    _HEADING = re.compile(r"^(#{1,6})[ \t]+(.+)$")
    _EXCLUDED_SECTION = re.compile(
        r"خارج\s+از\s+(?:محدوده|دامنه)|عدم\s+پشتیبانی|پشتیبانی\s+نشده"
        r"|غیرقابل\s+پشتیبانی|out[\s-]+of[\s-]+scope|not\s+supported"
        r"|non[\s-]+goals|excluded",
        re.IGNORECASE,
    )

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

    @classmethod
    def _evidence_lines(cls, chunk: str) -> list[str]:
        """Rank source-grounded bullet sentences without generating new facts.

        This is an opt-in Stage 10 experiment, not a claim that lexical
        salience approximates semantic importance for arbitrary documents.
        """
        ranked: list[tuple[int, int, int, str]] = []
        fenced = False
        # Keep Markdown section scope for bullets within this chunk.
        # An exclusion bullet without its heading is unsafe to interpret,
        # so this is a guarded experiment, not general PDF/DOCX coverage.
        sections: list[tuple[int, bool]] = []
        for index, raw in enumerate(chunk.splitlines()):
            line = raw.strip()
            if line.startswith("```"):
                fenced = not fenced
                continue
            if fenced:
                continue
            heading = cls._HEADING.match(line)
            if heading is not None:
                level = len(heading.group(1))
                while sections and sections[-1][0] >= level:
                    sections.pop()
                excluded = (
                    bool(sections and sections[-1][1])
                    or bool(cls._EXCLUDED_SECTION.search(heading.group(2)))
                )
                sections.append((level, excluded))
                continue
            if sections and sections[-1][1]:
                continue
            match = cls._BULLET.match(line)
            if match is None:
                continue
            sentence = cls._FIRST_SENTENCE.split(match.group(1), maxsplit=1)[0].strip()
            if not sentence or len(sentence) > 250:
                continue
            weight = (
                3 * bool(cls._OBLIGATION.search(sentence))
                + 2 * bool(cls._ACTION.search(sentence))
                + 2 * bool(cls._CODE.search(sentence))
                + bool(cls._DETAIL.search(sentence))
            )
            if weight:
                ranked.append((-weight, len(sentence), index, sentence))
        # Prefer concise, high-signal clauses; emit in original document order.
        chosen = sorted(ranked)[:cls._MAP_EVIDENCE_LINES]
        return [item[3] for item in sorted(chosen, key=lambda item: item[2])]

    async def _augment_map_async(self, source: str, summary: str) -> str:
        """Retain only exact source excerpts if the intermediate cap permits."""
        current = summary
        for sentence in self._evidence_lines(source):
            if sentence in current:
                continue
            candidate = current + "\n" + sentence
            if len(candidate) > self._provider.max_input_characters:
                continue
            if await asyncio.to_thread(
                self._output_fits, candidate, self._provider.max_output_tokens
            ):
                current = candidate
        return current

    async def _final_source_evidence_async(
        self, source_lines: list[str], final_budget: int
    ) -> str | None:
        """Make an optional extractive fallback from first-level source quotes.

        No benchmark reference facts or generated intermediate text are used.
        Source-order preference is intentional and must be evaluated on diverse
        real documents before it can ever become the default.
        """
        chosen: list[str] = []
        for sentence in source_lines:
            if sentence in chosen:
                continue
            candidate = "\n".join((*chosen, sentence))
            if len(candidate) > self._provider.max_input_characters:
                continue
            if await asyncio.to_thread(self._output_fits, candidate, final_budget):
                chosen.append(sentence)
        return "\n".join(chosen) if chosen else None

    async def summarize_async(
        self, text: str, summary_length: str = "medium",
        *, preserve_map_evidence: bool = False,
        source_grounded_final: bool = False,
    ) -> str:
        desired_budget = self.output_token_budget(summary_length)
        if type(preserve_map_evidence) is not bool or type(source_grounded_final) is not bool:
            raise SummarizationInputError("evidence trial flags must be booleans")
        if source_grounded_final and not preserve_map_evidence:
            raise SummarizationInputError("source_grounded_final requires preserve_map_evidence")
        try:
            current = self._chunker.normalize(text)
        except ChunkingInputError as error:
            raise SummarizationInputError("text must contain valid nonempty content") from error
        if len(current) > self._chunker.MAX_TEXT_CHARACTERS:
            # The same documented work budget applies to short and long paths.
            raise ChunkingLimitError("input exceeds chunking character budget")

        calls = 0
        first_level_source_evidence: list[str] = []

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

        for level in range(self.MAX_HIERARCHY_LEVELS):
            if await asyncio.to_thread(self._chunker.fits, current):
                result = await infer(current, desired_budget)
                # Re-encoding is not always token-identical to decoder IDs;
                # fail rather than silently trimming or claiming a false cap.
                if (len(result) > self._provider.max_input_characters or
                        not await asyncio.to_thread(self._output_fits, result, desired_budget)):
                    raise SummaryOutputLimitError("summary exceeds requested token budget")
                # Stage 10 experimental fallback: only verbatim excerpts from
                # original source chunks, never from generated reductions.
                if source_grounded_final and first_level_source_evidence:
                    source_only = await self._final_source_evidence_async(
                        first_level_source_evidence, desired_budget
                    )
                    if source_only is not None:
                        return source_only
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
                part = await infer(chunk, self._provider.max_output_tokens)
                if preserve_map_evidence:
                    part = await self._augment_map_async(chunk, part)
                    if source_grounded_final and level == 0:
                        # Only collect excerpts really retained in the first
                        # Map result, and sourced from original input.
                        for sentence in self._evidence_lines(chunk):
                            if sentence in part and sentence not in first_level_source_evidence:
                                first_level_source_evidence.append(sentence)
                parts.append(part)
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
