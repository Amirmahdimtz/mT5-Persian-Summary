"""Bounded, source-grounded lexical retrieval for Persian documents (Stage 11).

This service retrieves evidence only: it never invents an answer or invokes mT5.
Document locations come from the extractor, not from text similarity.
"""

from __future__ import annotations

import asyncio
import re
import unicodedata
from dataclasses import dataclass
from typing import Literal

from src.core.services.summarization.document_extraction_service import (
    DocumentExtractionService,
    DocumentSegment,
)
from src.infrastructure.di.inject import inject


class RetrievalInputError(ValueError):
    """Invalid query, evidence collection or retrieval limit."""


@dataclass(frozen=True, slots=True)
class EvidenceHit:
    segment: DocumentSegment
    score: float
    matched_terms: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RetrievalResult:
    status: Literal["found", "not_found", "ambiguous"]
    evidence: tuple[EvidenceHit, ...]


@inject
class DocumentRetrievalService:
    """Rank source segments without a generative model or external services.

    "ambiguous" means that multiple similarly relevant source passages
    contain different explicit numbers/dates or named people. It does not
    assert that the passages logically contradict each other; a later
    answerer must resolve that uncertainty using the returned evidence.
    """

    MAX_QUERY_CHARACTERS = 512
    MAX_TOP_K = 8
    MAX_SEGMENTS = 8192
    MAX_INDEX_CHARACTERS = DocumentExtractionService.MAX_TEXT_CHARACTERS
    _STOP_WORDS = frozenset({
        "از", "به", "در", "با", "و", "که", "را", "یا", "برای", "چه", "چند",
        "کدام", "است", "بود", "شد", "شده", "میشود", "می", "این", "آن",
        "یک", "آیا", "تا", "روی", "درباره", "مورد", "باشد", "بوده",
    })
    _PERSON = re.compile(r"(?:آقای|خانم)\s+([\u0600-\u06ff]+)")
    _DIGIT = re.compile(r"(?<!\w)[0-9]+(?!\w)")
    _TOKEN = re.compile(r"[^\W_]+", flags=re.UNICODE)
    _CHAR_MAP = str.maketrans({
        "ي": "ی", "ى": "ی", "ك": "ک", "ة": "ه", "ۀ": "ه",
        "۰": "0", "۱": "1", "۲": "2", "۳": "3", "۴": "4",
        "۵": "5", "۶": "6", "۷": "7", "۸": "8", "۹": "9",
        "٠": "0", "١": "1", "٢": "2", "٣": "3", "٤": "4",
        "٥": "5", "٦": "6", "٧": "7", "٨": "8", "٩": "9",
    })

    def __init__(self, document_extraction_service: DocumentExtractionService) -> None:
        self._extractor = document_extraction_service

    @classmethod
    def _normalized_tokens(cls, text: str) -> tuple[str, ...]:
        # Normalization is for matching only. Evidence text stays unchanged.
        normalized = unicodedata.normalize("NFKC", text).translate(cls._CHAR_MAP)
        normalized = normalized.replace("\u200c", " ").replace("\u200d", " ")
        normalized = "".join(
            char for char in normalized if unicodedata.category(char) != "Mn"
        )
        return tuple(cls._TOKEN.findall(normalized.casefold()))

    @classmethod
    def _query_terms(cls, query: str) -> tuple[str, ...]:
        if (not isinstance(query, str) or not query.strip() or
                len(query) > cls.MAX_QUERY_CHARACTERS or
                any(ord(c) < 32 and c not in "\t\r\n" for c in query)):
            raise RetrievalInputError("query must be nonempty printable text within 512 characters")
        terms = tuple(dict.fromkeys(
            item for item in cls._normalized_tokens(query)
            if item not in cls._STOP_WORDS
        ))
        if not terms:
            raise RetrievalInputError("query must contain at least one searchable term")
        return terms

    @staticmethod
    def _required_matches(query_size: int) -> int:
        return (query_size * 3 + 4) // 5  # ceil(60% of informative terms)

    @classmethod
    def _explicit_facts(cls, value: str) -> tuple[frozenset[str], frozenset[str]]:
        words = cls._normalized_tokens(value)
        normalized = " ".join(words)
        return (
            frozenset(cls._DIGIT.findall(normalized)),
            frozenset(cls._PERSON.findall(normalized)),
        )

    @classmethod
    def _possibly_conflicting(cls, first: EvidenceHit, second: EvidenceHit) -> bool:
        if first.matched_terms != second.matched_terms:
            return False
        if second.score < first.score * 0.85:
            return False
        first_nums, first_people = cls._explicit_facts(first.segment.text)
        second_nums, second_people = cls._explicit_facts(second.segment.text)
        return bool(
            (first_nums and second_nums and first_nums != second_nums)
            or (first_people and second_people and first_people != second_people)
        )

    def retrieve_segments(
        self, segments: tuple[DocumentSegment, ...] | list[DocumentSegment],
        query: str, *, top_k: int = 3,
    ) -> RetrievalResult:
        terms = self._query_terms(query)
        if type(top_k) is not int or not 1 <= top_k <= self.MAX_TOP_K:
            raise RetrievalInputError("top_k must be an integer from 1 to 8")
        if not isinstance(segments, (tuple, list)) or len(segments) > self.MAX_SEGMENTS:
            raise RetrievalInputError("evidence collection exceeds segment limit")
        if any(not isinstance(segment, DocumentSegment) for segment in segments):
            raise RetrievalInputError("all evidence items must be DocumentSegment values")
        if sum(len(segment.text) for segment in segments) > self.MAX_INDEX_CHARACTERS * 2:
            # Overlap may repeat characters but cannot grow without bound.
            raise RetrievalInputError("evidence collection exceeds character budget")

        hits: list[EvidenceHit] = []
        for segment in segments:
            haystack = self._normalized_tokens(segment.text)
            if not haystack:
                continue
            vocabulary = set(haystack)
            found = tuple(term for term in terms if term in vocabulary)
            if len(found) < self._required_matches(len(terms)):
                continue
            coverage = len(found) / len(terms)
            phrase = " ".join(terms) in " ".join(haystack)
            score = 5.0 * coverage + 0.25 * len(found) + (2.0 if phrase else 0.0)
            hits.append(EvidenceHit(segment, score, found))
        hits.sort(key=lambda hit: (-hit.score, hit.segment.document_order))
        if not hits:
            return RetrievalResult("not_found", ())

        chosen = tuple(hits[:top_k])
        # Check one candidate beyond top_k, including when top_k=1.
        conflicting = any(
            self._possibly_conflicting(hits[0], candidate)
            for candidate in hits[1: min(len(hits), max(2, top_k + 1))]
        )
        return RetrievalResult("ambiguous" if conflicting else "found", chosen)

    async def retrieve_async(
        self, content: bytes, filename: str, query: str, *, top_k: int = 3,
    ) -> RetrievalResult:
        # Fail input validation before parsing an untrusted file.
        self._query_terms(query)
        if type(top_k) is not int or not 1 <= top_k <= self.MAX_TOP_K:
            raise RetrievalInputError("top_k must be an integer from 1 to 8")
        segments = await asyncio.to_thread(self._extractor.extract_segments, content, filename)
        return await asyncio.to_thread(self.retrieve_segments, segments, query, top_k=top_k)
