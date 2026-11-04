"""Bounded, source-grounded lexical retrieval for Persian documents (Stage 11).

This service retrieves evidence only: it never invents an answer or invokes mT5.
Document locations come from the extractor, not from text similarity.
"""

from __future__ import annotations

import asyncio
import math
import re
import unicodedata
from collections import Counter
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
        "چرا", "چگونه", "چطور", "چیست", "هست", "بر", "اساس", "طبق",
        "نمی", "بدون", "باعث", "کرد", "کند", "کنند", "بودند", "دارد",
        "دارند", "ها", "های", "هایی", "هم", "نیز", "لزوما", "فقط",
        "چقدر", "زمانی", "کسی", "چیزی", "وقتی", "اند", "هستند",
    })
    _PERSON = re.compile(r"(?:آقای|خانم)\s+([\u0600-\u06ff]+)")
    _DIGIT = re.compile(r"(?<!\w)[0-9]+(?!\w)")
    _TOKEN = re.compile(r"[^\W_]+", flags=re.UNICODE)
    _ANSWER_NUMBER_INTENT = re.compile(
        r"چقدر|مبلغ|تعداد|چند|واحد|موارد|درآمد|سود|نرخ|نسبت|درصد|بیشترین|چه\s+تاریخ"
        r"|(?:دو|سه|چهار|پنج|شش|هفت)\s+(?:معیار|محور|دلیل|مورد|عامل)"
    )
    _PERCENT_INTENT = re.compile(r"نسبت|درصد|سهم|رشد")
    _PERCENT_FACT = re.compile(r"درصد|[%٪]")
    _SECTION_HEADING = re.compile(r"^\[[^\]\r\n]{1,24}\]\s+\S")
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
        """Normalize matching keys while preserving original source excerpts."""
        normalized = unicodedata.normalize("NFKC", text).translate(cls._CHAR_MAP)
        normalized = normalized.replace("\u200c", " ").replace("\u200d", " ")
        normalized = "".join(
            char for char in normalized if unicodedata.category(char) != "Mn"
        )
        tokens: list[str] = []
        for token in cls._TOKEN.findall(normalized.casefold()):
            if len(token) >= 7 and token.endswith("هایی"):
                token = token[:-4]
            elif len(token) >= 6 and token.endswith("های"):
                token = token[:-3]
            elif len(token) >= 5 and token.endswith("ها"):
                token = token[:-2]
            if len(token) >= 6 and token.endswith("ی") and not token.isdecimal():
                token = token[:-1]
            tokens.append(token)
        return tuple(tokens)

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
        return 1 if query_size == 1 else 2  # paraphrases need flexible literal coverage

    @staticmethod
    def _context_key(segment: DocumentSegment) -> tuple | None:
        """Only genuine shared paragraphs/table rows provide ranking context."""
        loc = segment.source_location
        if loc.paragraph is not None:
            return (loc.document_type, "paragraph", loc.paragraph)
        if loc.table is not None and loc.row is not None:
            return (loc.document_type, "table_row", loc.table, loc.row)
        # PDF pages may contain unrelated topics: never group an entire page.
        return None

    @classmethod
    def _numeric_score(cls, query: str, query_terms: tuple[str, ...], text: str) -> float:
        """Prefer requested quantities to nearby, unrelated percentages."""
        if not cls._ANSWER_NUMBER_INTENT.search(query):
            return 0.0
        source_numbers = {x for x in cls._normalized_tokens(text) if x.isdecimal()}
        question_numbers = {x for x in query_terms if x.isdecimal()}
        extra_numbers = {
            x for x in source_numbers - question_numbers
            if not (len(x) == 4 and (1300 <= int(x) <= 1499 or 1900 <= int(x) <= 2099))
        }
        value = 1.3 if extra_numbers else 0.0
        if re.search(r"(?:دو|سه|چهار|پنج|شش|هفت)\s+(?:معیار|محور|دلیل|مورد|عامل)", query):
            count_words = {"دو", "سه", "چهار", "پنج", "شش", "هفت"}
            if count_words.intersection(cls._normalized_tokens(query)).intersection(
                cls._normalized_tokens(text)
            ):
                value += 1.0
        if len(extra_numbers) >= 2:
            value += 0.3
        if cls._PERCENT_FACT.search(text) and not cls._PERCENT_INTENT.search(query):
            value -= 1.5
        return value

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

        vocabularies: list[set[str]] = []
        frequencies: Counter[str] = Counter()
        contexts: dict[tuple, set[str]] = {}
        section_contexts: dict[int, set[str]] = {}
        sections: list[int | None] = []
        active_section: int | None = None
        for segment in segments:
            vocabulary = set(self._normalized_tokens(segment.text))
            vocabularies.append(vocabulary)
            frequencies.update(vocabulary)
            key = self._context_key(segment)
            if key is not None:
                contexts.setdefault(key, set()).update(vocabulary)
            # DOCX headings may be plain paragraphs; context is not answer text.
            if (segment.source_location.document_type == "docx"
                    and len(segment.text) <= 140
                    and self._SECTION_HEADING.match(segment.text)):
                active_section = segment.document_order
                section_contexts[active_section] = set(vocabulary)
            sections.append(active_section if segment.source_location.document_type == "docx" else None)
            if active_section is not None and segment.source_location.document_type == "docx":
                section_contexts[active_section].update(vocabulary)
        count = len(segments)
        weights = {
            term: math.log1p((count + 1) / (frequencies[term] + 1))
            for term in terms
        }
        total_weight = sum(weights.values())
        hits: list[EvidenceHit] = []
        for segment, vocabulary, section in zip(segments, vocabularies, sections):
            if (not vocabulary or
                    (segment.source_location.document_type == "docx"
                     and self._SECTION_HEADING.match(segment.text))):
                continue
            found = tuple(term for term in terms if term in vocabulary)
            key = self._context_key(segment)
            context = contexts.get(key, vocabulary) if key is not None else vocabulary
            if section is not None:
                context = context | section_contexts[section]
            context_found = tuple(term for term in terms if term in context)
            if len(context_found) < self._required_matches(len(terms)) or not found:
                continue
            direct_coverage = sum(weights[t] for t in found) / total_weight
            context_coverage = sum(weights[t] for t in context_found) / total_weight
            phrase = " ".join(terms) in " ".join(self._normalized_tokens(segment.text))
            score = (
                5.0 * direct_coverage + 3.0 * context_coverage
                + 0.2 * len(found) + (1.0 if phrase else 0.0)
                + self._numeric_score(query, terms, segment.text)
            )
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
