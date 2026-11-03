"""Evidence-only document questioning and topic-focused summaries (Stage 12)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from src.core.services.summarization.document_extraction_service import SourceLocation
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
    _DATE_INTENT = re.compile(r"تاریخ|زمان|روز|ماه|چه\s+وقت|کی\b")
    _PERSON_INTENT = re.compile(r"چه\s+کسی|مسئول|نام\s+(?:فرد|شخص)|به\s+عهده")
    _AMOUNT_INTENT = re.compile(r"چقدر|چند\b|مبلغ|بودجه|تعداد|هزینه")
    _DATE_FACT = re.compile(
        r"(?:[0-9۰-۹٠-٩]{1,4}\s+(?:فروردین|اردیبهشت|خرداد|تیر|مرداد|شهریور|مهر|آبان|آذر|دی|بهمن|اسفند))"
        r"|(?:فروردین|اردیبهشت|خرداد|تیر|مرداد|شهریور|مهر|آبان|آذر|دی|بهمن|اسفند)"
        r"|(?:[0-9۰-۹٠-٩]{4}[-/][0-9۰-۹٠-٩]{1,2}[-/][0-9۰-۹٠-٩]{1,2})"
    )
    _PERSON_FACT = re.compile(r"(?:آقای|خانم)\s+[\u0600-\u06ff]+")
    _AMOUNT_FACT = re.compile(r"[0-9۰-۹٠-٩]|\b(?:یک|دو|سه|چهار|پنج|شش|هفت|هشت|نه|ده)\b")

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
        covered = len(set(terms).intersection(hit.matched_terms))
        if covered * 4 < len(terms) * 3:  # at least 75% meaningful coverage
            return False
        source = hit.segment.text
        if cls._DATE_INTENT.search(query) and not cls._DATE_FACT.search(source):
            return False
        if cls._PERSON_INTENT.search(query) and not cls._PERSON_FACT.search(source):
            return False
        if cls._AMOUNT_INTENT.search(query) and not cls._AMOUNT_FACT.search(source):
            return False
        return True

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
        result = await self._retriever.retrieve_async(content, filename, query, top_k=6)
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
            top = supported[0]
            if len(top.segment.text) > self.MAX_ANSWER_CHARACTERS:
                return DocumentQueryResult("not_found", mode, query, None, ())
            # Quoting the exact source passage is safer than generating a
            # person, amount, date or polarity transformation from it.
            return DocumentQueryResult(
                "found", mode, query, top.segment.text,
                (self._source_evidence(top),),
            )

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
