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
    _LEAD_QUANTITY = re.compile(r"\b(?:یک|دو|سه|چهار|پنج|شش|هفت|هشت|نه|ده|[0-9۰-۹]+)\b")
    _LEAD_CAPABILITY = re.compile(
        r"پشتیبانی|می‌توان|می‌شود|می‌شوند|بتواند|توانایی|support", re.IGNORECASE
    )
    _LEAD_TECH = re.compile(r"`[^`]+`|(?<!\w)[A-Z]{2,}(?!\w)")
    _MAX_LEAD_CANDIDATES = 32
    _MAX_LEAD_FINAL_SENTENCES = 3
    _MAX_SOURCE_SENTENCES = 64
    _SOURCE_SENTENCE_LIMITS = {"short": 1, "medium": 3, "long": 6}
    _SOURCE_SIGNAL = re.compile(
        r"افزایش|کاهش|برگزار|تعیین|تصمیم|توصیه|موظف|مسئول|"
        r"اولویت|برنامه|امضا|توسعه|افتتاح|بازنگری|مرحله|"
        r"اجرا|پشتیبانی|آموزش|آغاز|پایان"
    )
    _HEADING = re.compile(r"^(#{1,6})[ \t]+(.+)$")
    # pypdf layout mode may retain visual numbered headings as ordinary lines.
    _NUMBERED_HEADING = re.compile(r"^[0-9۰-۹]{1,2}\s*[.)．]\s+\S.{0,70}$")
    _EXCLUDED_SECTION = re.compile(
        r"خارج\s+از\s+(?:محدوده|دامنه)|عدم\s+پشتیبانی|پشتیبانی\s+نشده"
        r"|غیرقابل\s+پشتیبانی|out[\s-]+of[\s-]+scope|not\s+supported"
        r"|non[\s-]+goals|excluded|backlog|نه\s+بخشی\s+از"
        r"|برنامه(?:‌|\s)*های\s+آینده|امکانات\s+آینده"
        r"|future\s+work|planned\s+features|post[\s-]*mvp",
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

    @classmethod
    def _excluded_original_clauses(cls, text: str) -> set[str]:
        """Filter original-source exclusion bullets even across chunk splits.

        This final-output check operates on the full original document,
        so a heading separated from its bullet by chunking is still honored.
        """
        sections: list[tuple[int, bool]] = []
        fenced = False
        excluded: set[str] = set()
        for raw in text.splitlines():
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
                sections.append((
                    level,
                    bool(sections and sections[-1][1])
                    or bool(cls._EXCLUDED_SECTION.search(heading.group(2))),
                ))
                continue
            if not sections or not sections[-1][1]:
                continue
            bullet = cls._BULLET.match(line)
            if bullet is None:
                continue
            sentence = cls._FIRST_SENTENCE.split(bullet.group(1), maxsplit=1)[0].strip()
            if sentence:
                excluded.add(sentence)
        return excluded

    @classmethod
    def _lead_source_sentences(cls, source: str) -> list[str]:
        """Extract preface/first-section prose verbatim, respecting heading scope."""
        result: list[str] = []
        fenced = False
        seen_major = False
        scopes: list[tuple[int, bool]] = []
        for raw in source.splitlines():
            line = raw.strip()
            if line.startswith("```"):
                fenced = not fenced
                continue
            if fenced or not line or line == "---":
                continue
            heading = cls._HEADING.match(line)
            if heading:
                level = len(heading.group(1))
                if level == 2:
                    if seen_major:
                        break
                    seen_major = True
                while scopes and scopes[-1][0] >= level:
                    scopes.pop()
                scopes.append((
                    level,
                    bool(scopes and scopes[-1][1])
                    or bool(cls._EXCLUDED_SECTION.search(heading.group(2))),
                ))
                continue
            if scopes and scopes[-1][1]:
                continue
            if line.startswith(("-", "*", "•", "|", "~~~")):
                continue
            if line.startswith(">"):
                line = line.lstrip(">").strip()
            if not line or line.startswith("#"):
                continue
            for candidate in cls._FIRST_SENTENCE.split(line):
                sentence = candidate.strip()
                if (24 <= len(sentence) <= 300 and
                        re.search(r"[\u0600-\u06ff]", sentence) and
                        sentence not in result):
                    result.append(sentence)
                    if len(result) >= cls._MAX_LEAD_CANDIDATES:
                        return result
        return result

    async def _balanced_lead_final_async(
        self, original_source: str, final_budget: int
    ) -> str | None:
        """Optional v4: favor informative, concise, exact source prose sentences.

        Never read reference facts or summaries. Each complete emitted sentence
        is verified against the final tokenizer ceiling, including specials.
        """
        ranked: list[tuple[float, int, int, str]] = []
        for position, sentence in enumerate(self._lead_source_sentences(original_source)):
            raw_score = (
                5 * bool(self._LEAD_CAPABILITY.search(sentence))
                + 4 * bool(self._LEAD_QUANTITY.search(sentence))
                + min(3, len(self._LEAD_TECH.findall(sentence)))
            )
            if not raw_score:
                continue
            if len(sentence) > self._provider.max_input_characters:
                continue
            tokens = await asyncio.to_thread(self._provider.count_input_tokens, sentence)
            if tokens <= 0 or tokens > final_budget:
                continue
            ranked.append((-raw_score / tokens, tokens, position, sentence))
        ranked.sort()
        chosen: list[tuple[int, str]] = []
        for _density, _tokens, position, sentence in ranked:
            if len(chosen) >= self._MAX_LEAD_FINAL_SENTENCES:
                break
            tentative = sorted((*chosen, (position, sentence)))
            candidate = "\n".join(part for _, part in tentative)
            if (len(candidate) <= self._provider.max_input_characters and
                    await asyncio.to_thread(self._output_fits, candidate, final_budget)):
                chosen = tentative
        return "\n".join(part for _, part in chosen) if chosen else None

    @classmethod
    def _source_sentence_candidates(cls, source: str) -> list[tuple[int, str]]:
        """Find complete source sentences across PDF layout-wrapped lines.

        Rejoin physical lines only inside a single source paragraph or list
        item. Preserve section/fence boundaries, source order and full clauses;
        no generated facts or unbounded text expansion. The joined text is
        whitespace-normalized, not guaranteed to be a byte-exact substring.
        """
        results: list[tuple[int, str]] = []
        seen: set[str] = set()
        scopes: list[tuple[int, bool]] = []
        fenced = False
        paragraph = 0
        blank_run = 0
        lines: list[str] = []

        def flush_paragraph() -> bool:
            if not lines:
                return False
            joined = " ".join(lines)
            lines.clear()
            for sentence in cls._FIRST_SENTENCE.split(joined):
                value = sentence.strip()
                if (not value or value[-1] not in ".!?؟؛" or
                        not 12 <= len(value) <= 350 or
                        not re.search(r"[\u0600-\u06ff]", value) or
                        value in seen):
                    continue
                seen.add(value)
                results.append((paragraph, value))
                if len(results) >= cls._MAX_SOURCE_SENTENCES:
                    return True
            return False

        for raw in source.splitlines():
            line = raw.strip()
            if not line:
                blank_run += 1
                # PDF layout text frequently inserts one blank line between
                # two display-wrapped halves of the same logical sentence.
                # Two blank lines, or a completed sentence, mark a boundary.
                if (blank_run >= 2 or
                        (lines and lines[-1].endswith((".", "!", "?", "؟", "؛")))):
                    if flush_paragraph():
                        return results
                    paragraph += 1
                continue
            blank_run = 0
            if cls._NUMBERED_HEADING.match(line):
                if flush_paragraph():
                    return results
                paragraph += 1
                continue
            if line.startswith("```"):
                if flush_paragraph():
                    return results
                fenced = not fenced
                paragraph += 1
                continue
            if fenced:
                continue
            if line.startswith(("|", "~~~")):
                if flush_paragraph():
                    return results
                paragraph += 1
                continue
            heading = cls._HEADING.match(line)
            if heading:
                if flush_paragraph():
                    return results
                level = len(heading.group(1))
                while scopes and scopes[-1][0] >= level:
                    scopes.pop()
                scopes.append((
                    level,
                    bool(scopes and scopes[-1][1])
                    or bool(cls._EXCLUDED_SECTION.search(heading.group(2))),
                ))
                paragraph += 1
                continue
            if scopes and scopes[-1][1]:
                if flush_paragraph():
                    return results
                continue
            bullet = cls._BULLET.match(line)
            if bullet:
                if flush_paragraph():
                    return results
                paragraph += 1
                line = bullet.group(1)
            elif line.startswith(">"):
                line = line.lstrip(">").strip()
            if line.startswith("#"):
                if flush_paragraph():
                    return results
                continue
            if line:
                lines.append(line)
        flush_paragraph()
        return results

    async def _source_sentence_final_async(
        self, original_source: str, summary_length: str, final_budget: int
    ) -> str | None:
        """v5 trial: evidence-only bounded final across direct and long inputs.

        This is an explicit extractive alternative, NOT an mT5 decoding fix.
        Exact source sentences are emitted unchanged and in source order.
        """
        candidates = self._source_sentence_candidates(original_source)
        ranked: list[tuple[int, int, int, str]] = []
        for position, (paragraph, sentence) in enumerate(candidates):
            if len(sentence) > self._provider.max_input_characters:
                continue
            token_count = await asyncio.to_thread(
                self._provider.count_input_tokens, sentence
            )
            if token_count < 1 or token_count > final_budget:
                continue
            score = (
                3 * bool(self._SOURCE_SIGNAL.search(sentence))
                + 2 * bool(self._LEAD_QUANTITY.search(sentence))
                + bool(self._LEAD_TECH.search(sentence))
                + bool(self._OBLIGATION.search(sentence))
            )
            ranked.append((score, position, paragraph, sentence))

        chosen: list[tuple[int, int, str]] = []
        count_limit = self._SOURCE_SENTENCE_LIMITS[summary_length]
        used_paragraphs: set[int] = set()
        while len(chosen) < count_limit:
            eligible = sorted(
                (entry for entry in ranked if entry[1] not in {x[0] for x in chosen}),
                key=lambda item: (
                    -(item[0] + (3 if item[2] not in used_paragraphs else 0)),
                    item[1],
                ),
            )
            accepted = None
            for _score, position, paragraph, sentence in eligible:
                tentative = sorted((*chosen, (position, paragraph, sentence)))
                candidate = "\n".join(part for _, _, part in tentative)
                if (len(candidate) <= self._provider.max_input_characters and
                        await asyncio.to_thread(self._output_fits, candidate, final_budget)):
                    accepted = (position, paragraph, sentence)
                    break
            if accepted is None:
                break
            chosen.append(accepted)
            used_paragraphs.add(accepted[1])
        return (
            "\n".join(part for _, _, part in sorted(chosen))
            if chosen else None
        )

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
        balanced_source_final: bool = False,
        source_sentence_final: bool = False,
    ) -> str:
        desired_budget = self.output_token_budget(summary_length)
        if any(type(flag) is not bool for flag in (
            preserve_map_evidence, source_grounded_final,
            balanced_source_final, source_sentence_final
        )):
            raise SummarizationInputError("evidence trial flags must be booleans")
        if source_grounded_final and not preserve_map_evidence:
            raise SummarizationInputError("source_grounded_final requires preserve_map_evidence")
        if balanced_source_final and not source_grounded_final:
            raise SummarizationInputError("balanced_source_final requires source_grounded_final")
        if source_sentence_final and not balanced_source_final:
            raise SummarizationInputError("source_sentence_final requires balanced_source_final")
        try:
            current = self._chunker.normalize(text)
        except ChunkingInputError as error:
            raise SummarizationInputError("text must contain valid nonempty content") from error
        if len(current) > self._chunker.MAX_TEXT_CHARACTERS:
            # The same documented work budget applies to short and long paths.
            raise ChunkingLimitError("input exceeds chunking character budget")

        calls = 0
        first_level_source_evidence: list[str] = []
        original_source = current
        if source_sentence_final:
            extractive = await self._source_sentence_final_async(
                original_source, summary_length, desired_budget
            )
            if extractive is None:
                raise SummarizationNoProgressError(
                    "no complete source sentence fits requested token budget"
                )
            return extractive
        excluded_original_clauses = (
            self._excluded_original_clauses(current) if source_grounded_final else set()
        )

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
                if balanced_source_final and first_level_source_evidence:
                    prose_only = await self._balanced_lead_final_async(
                        original_source, desired_budget
                    )
                    if prose_only is not None:
                        return prose_only
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
                            if (
                                sentence in part
                                and sentence not in first_level_source_evidence
                                and sentence not in excluded_original_clauses
                            ):
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
