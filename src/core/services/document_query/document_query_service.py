"""Evidence-only document questioning and topic-focused summaries (Stage 12)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from src.core.services.summarization.document_extraction_service import SourceLocation
from src.core.services.document_query.answer_validation import DocumentAnswerValidator
from src.core.services.summarization.document_retrieval_service import (
    DocumentRetrievalService,
    EvidenceHit,
    RetrievalInputError,
)
from src.infrastructure.di.inject import inject

QueryMode = Literal["answer", "focused_summary"]
SummaryLength = Literal["short", "medium", "long"]
QueryStatus = Literal["found", "not_found", "ambiguous"]


class DocumentQueryInputError(ValueError):
    """The document-query mode or length is invalid."""


@dataclass(frozen=True, slots=True)
class SourceEvidence:
    text: str
    source_location: SourceLocation
    document_order: int


@dataclass(frozen=True, slots=True)
class DocumentQueryResult:
    status: QueryStatus
    mode: QueryMode
    query: str
    answer: str | None
    evidence: tuple[SourceEvidence, ...]


@inject
class DocumentQueryService:
    """Return extractive, source-verifiable facts without model generation.

    Retriever status is a candidate signal, not a license to answer. A factual
    question requires explicit time, person or quantity evidence as relevant.
    Potentially conflicting hits produce no answer; their source excerpts are
    retained so the caller can inspect the ambiguity.
    """

    MAX_ANSWER_CHARACTERS = 1200
    _SUMMARY_BUDGETS = {"short": 320, "medium": 680, "long": 1200}
    _QUESTION_FILLERS = frozenset({
        "کسی", "زمانی", "چطور", "چگونه", "چقدر", "چیست", "هست", "کی",
    })
    _DATE_INTENT = DocumentAnswerValidator._DATE_INTENT
    _PERSON_INTENT = re.compile(r"چه\s+کسی|مسئول|نام\s+(?:فرد|شخص)|به\s+عهده")
    _AMOUNT_INTENT = re.compile(r"چقدر|چند\b|مبلغ|بودجه|تعداد|هزینه")
    _DATE_FACT = DocumentAnswerValidator._DATE_FACT
    _PERSON_FACT = re.compile(r"(?:آقای|خانم)\s+[\u0600-\u06ff]+")
    _AMOUNT_FACT = re.compile(r"[0-9۰-۹٠-٩]|\b(?:یک|دو|سه|چهار|پنج|شش|هفت|هشت|نه|ده)\b")
    _MULTIPART = re.compile(r"(?:^|\s)(?:دو|سه|چهار)(?:\s|$)|\sو\s")
    MAX_ANSWER_EXCERPTS = 7

    def __init__(self, document_retrieval_service: DocumentRetrievalService) -> None:
        self._retriever = document_retrieval_service

    @staticmethod
    def validate_query(query: str) -> None:
        """Validate lexical search terms before reading uploaded file bytes."""
        DocumentRetrievalService._query_terms(query)

    @staticmethod
    def _source_evidence(hit: EvidenceHit) -> SourceEvidence:
        segment = hit.segment
        return SourceEvidence(segment.text, segment.source_location, segment.document_order)

    @classmethod
    def _has_factual_support(cls, query: str, hit: EvidenceHit) -> bool:
        """Conservative query-intent support; no answer interpolation."""
        # Candidate ranking admits partial lexical matches. Do not answer a
        # question solely because an unrelated clause shares a generic noun.
        terms = tuple(
            term for term in DocumentRetrievalService._query_terms(query)
            if term not in cls._QUESTION_FILLERS
        )
        if not terms:
            return False
        covered = len(set(terms).intersection(hit.matched_terms + hit.heading_terms))
        if (covered < DocumentRetrievalService._required_matches(len(terms))
                and not (DocumentAnswerValidator._CONDITIONAL_TIME.search(query)
                         and covered >= 1)):
            return False
        source = hit.segment.text
        if (cls._DATE_INTENT.search(query) and not cls._DATE_FACT.search(source)
                and not DocumentAnswerValidator._CONDITIONAL_TIME.search(query)):
            return False
        if cls._PERSON_INTENT.search(query) and not cls._PERSON_FACT.search(source):
            return False
        if cls._AMOUNT_INTENT.search(query) and not cls._AMOUNT_FACT.search(source):
            return False
        return True

    @classmethod
    def _source_neighbors(cls, top: EvidenceHit, segments: tuple) -> tuple:
        """Bounded source-exact neighboring sentences for multipart answers.

        TXT and DOCX stay inside the real paragraph; PDF uses short page-local
        windows without crossing explicit section boundaries.
        """
        if not segments:
            return (top.segment,)
        index = top.segment.document_order
        if not 0 <= index < len(segments):
            return (top.segment,)
        loc = top.segment.source_location
        if loc.paragraph is not None:
            # A styled DOCX section can contain a multi-paragraph answer.
            # Never cross into another section or include a table accidentally.
            if loc.document_type == "docx" and loc.section:
                candidates = [
                    seg for seg in segments
                    if (seg.source_location.document_type == "docx"
                        and seg.source_location.section == loc.section
                        and seg.source_location.paragraph is not None
                        and abs(seg.source_location.paragraph - loc.paragraph) <= 6)
                ]
            else:
                candidates = [
                    seg for seg in segments
                    if (seg.source_location.document_type == loc.document_type
                        and seg.source_location.paragraph == loc.paragraph
                        and seg.source_location.table == loc.table)
                ]
        elif loc.table is not None:
            candidates = [
                seg for seg in segments
                if (seg.source_location.table == loc.table
                    and seg.source_location.row == loc.row)
            ]
        else:
            start = index
            while (not cls._is_section_header(top.segment.text)
                   and start > 0 and index - start < 2):
                previous = segments[start - 1]
                if previous.source_location.page != loc.page:
                    break
                start -= 1
                if cls._is_section_header(previous.text):
                    break
            stop = index + 1
            while stop < len(segments) and stop - index <= 4:
                candidate = segments[stop]
                if (candidate.source_location.page != loc.page
                        or cls._is_section_header(candidate.text)):
                    break
                stop += 1
            candidates = segments[start:stop]

        chosen = []
        used = 0
        for segment in candidates:
            length = len(segment.text) + (1 if chosen else 0)
            if (len(chosen) >= cls.MAX_ANSWER_EXCERPTS
                    or used + length > cls.MAX_ANSWER_CHARACTERS):
                continue
            chosen.append(segment)
            used += length
        return tuple(chosen) if top.segment in chosen else (top.segment,)

    @staticmethod
    def _is_section_header(text: str) -> bool:
        return bool(re.search(
            r"(?:\[\s*(?:[A-Z]\d{2}|\d{2}[A-Z])\s*\]"
            r"|\]\s*(?:[A-Z]\d{2}|\d{2}[A-Z])\s*\[)",
            text[:125],
        ))

    async def query_file_async(
        self,
        content: bytes,
        filename: str,
        query: str,
        *,
        mode: QueryMode = "answer",
        summary_length: SummaryLength | None = None,
    ) -> DocumentQueryResult:
        if mode not in ("answer", "focused_summary") or not isinstance(mode, str):
            raise DocumentQueryInputError("mode must be answer or focused_summary")
        if mode == "answer" and summary_length is not None:
            raise DocumentQueryInputError("summary_length is only valid for focused_summary")
        if mode == "focused_summary" and summary_length not in (None, *self._SUMMARY_BUDGETS):
            raise DocumentQueryInputError("summary_length must be short, medium or long")
        # Input validation occurs before parsing untrusted document bytes.
        self.validate_query(query)
        result = await self._retriever.retrieve_async(content, filename, query, top_k=8)
        if result.status == "not_found" or not result.evidence:
            return DocumentQueryResult("not_found", mode, query, None, ())

        # Return all top conflicting excerpts, not just a single misleading
        # answer. Stage 11's ambiguous status is intentionally conservative.
        if result.status == "ambiguous":
            return DocumentQueryResult(
                "ambiguous", mode, query, None,
                tuple(self._source_evidence(hit) for hit in result.evidence),
            )

        supported = tuple(hit for hit in result.evidence if self._has_factual_support(query, hit))
        if not supported:
            return DocumentQueryResult("not_found", mode, query, None, ())

        if mode == "answer":
            # Retrieval identifies candidates; validation decides answerability.
            # Inspect up to the retriever's bounded eight ranked candidates.
            for hit in supported:
                if len(hit.segment.text) > self.MAX_ANSWER_CHARACTERS:
                    continue
                excerpts = (self._source_neighbors(hit, result.source_segments)
                            if self._MULTIPART.search(query) else (hit.segment,))
                if not DocumentAnswerValidator.supports(query, excerpts):
                    continue
                contradictions = DocumentAnswerValidator.conflicting_percent_evidence(
                    query, excerpts, result.source_segments
                )
                if contradictions:
                    return DocumentQueryResult(
                        "ambiguous", mode, query, None,
                        tuple(SourceEvidence(
                            seg.text, seg.source_location, seg.document_order
                        ) for seg in contradictions),
                    )
                return DocumentQueryResult(
                    "found", mode, query,
                    "\n".join(seg.text for seg in excerpts),
                    tuple(SourceEvidence(
                        seg.text, seg.source_location, seg.document_order
                    ) for seg in excerpts),
                )
            return DocumentQueryResult("not_found", mode, query, None, ())

        budget = self._SUMMARY_BUDGETS[summary_length or "medium"]
        selected: list[EvidenceHit] = []
        used = 0
        for hit in sorted(supported, key=lambda h: h.segment.document_order):
            length = len(hit.segment.text) + (1 if selected else 0)
            if used + length <= budget:
                selected.append(hit)
                used += length
        if not selected:
            return DocumentQueryResult("not_found", mode, query, None, ())
        text = "\n".join(hit.segment.text for hit in selected)
        return DocumentQueryResult(
            "found", mode, query, text,
            tuple(self._source_evidence(hit) for hit in selected),
        )
