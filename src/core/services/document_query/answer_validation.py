"""Conservative evidence checks for extractive Persian document answers.

This pure helper never generates text, accesses external services or receives an
answer key. It may abstain when the requested fact cannot be verified.
"""

from __future__ import annotations

import re

from src.core.services.summarization.document_retrieval_service import DocumentRetrievalService


class DocumentAnswerValidator:
    """Validate requested answer slots and independently check rate conflicts."""

    _DATE_INTENT = re.compile(r"تاریخ|چه\s+(?:زمانی|روز|ماه|وقت)|در\s+چه\s+(?:زمانی|روز|ماه|وقت)|کی\b")
    _DATE_FACT = re.compile(
        r"(?:[0-9۰-۹٠-٩]{1,4}\s+(?:فروردین|اردیبهشت|خرداد|تیر|مرداد|شهریور|مهر|آبان|آذر|دی|بهمن|اسفند|ژانویه|فوریه|مارس|آوریل|مه|ژوئن|ژوئیه|اوت|سپتامبر|اکتبر|نوامبر|دسامبر))"
        r"|(?:فروردین|اردیبهشت|خرداد|تیر|مرداد|شهریور|مهر|آبان|آذر|دی|بهمن|اسفند|ژانویه|فوریه|مارس|آوریل|مه|ژوئن|ژوئیه|اوت|سپتامبر|اکتبر|نوامبر|دسامبر)"
        r"|(?:[0-9۰-۹٠-٩]{4}[-/][0-9۰-۹٠-٩]{1,2}[-/][0-9۰-۹٠-٩]{1,2})"
    )
    # Check the requested slot, not mere topical similarity or unrelated digits.
    _IP_QUESTION = re.compile(r"(?:آدرس|نشانی)\s*(?:IP|آی\s*پی)|\bIP\b", re.I)
    _IP_FACT = re.compile(r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b|\b(?:[a-f0-9]{1,4}:){2,}[a-f0-9:]+\b", re.I)
    _IDENTIFIER_QUESTION = re.compile(r"(?:شماره|شناسه|کد)\s+(?![0-9۰-۹])[^\W\d_]+")
    _IDENTIFIER_FACT = re.compile(r"(?:شماره|شناسه|کد)\s*(?:[\w\u0600-\u06ff]{1,20}\s+){0,3}[:：-]?\s*[0-9۰-۹][\w\-/]*")
    _MODEL_QUESTION = re.compile(r"(?:مدل|تیپ)\s+(?:\S+)")
    _MODEL_FACT = re.compile(r"(?:مدل|تیپ)\s*[:：]?\s*[\w\-/]{2,}")
    _COMPANY_NAME_QUESTION = re.compile(r"(?:نام|اسم)\s+(?:(?:شرکت|تأمین[\u200c -]*کننده|تامین[\u200c -]*کننده|سازنده))")
    _COMPANY_NAME_FACT = re.compile(r"(?:شرکت|تأمین[\u200c -]*کننده|تامین[\u200c -]*کننده|سازنده)\s+(?:[\u0600-\u06ff\w-]{2,}\s*){1,3}")
    _CONDITIONAL_TIME = re.compile(r"چه\s+زمانی.*(?:اجازه|ترخیص|مجاز|امکان)|چه\s+شرطی")
    _CONDITION_FACT = re.compile(r"(?:پس\s+از|در\s+صورت|مشروط\s+به|تنها\s+اگر|فقط\s+پس\s+از)")
    _PERCENT = re.compile(r"([0-9۰-۹٠-٩]+(?:[٫.][0-9۰-۹٠-٩]+)?)\s*(?:درصد|[%٪])")
    _NUMERIC = re.compile(r"[0-9۰-۹٠-٩][0-9۰-۹٠-٩٬,٫.]*")
    _FOCUS_STOP = frozenset({
        "این", "سند", "گزارش", "چند", "چه", "چقدر", "چهار", "سه", "دو",
        "بود", "در", "از", "با", "به", "که", "برای", "بر", "شود",
        "شد", "چگونه", "آیا", "زمان", "زمانی", "اولیه", "نهایی",
        "سهم", "مورد", "تفاوت", "بودند", "است", "سال", "سالهای",
        "هم", "تعداد", "میزان", "آن", "آنها", "آنهاست", "ارقام", "کدام",
        "کند", "قرار", "دارد", "اند", "نیز", "ثبت", "کرده", "یکی",
        "اگر", "بیشتر", "حد", "مجاز", "انجام", "کار", "داشت", "عدد",
        "بازه", "تاریخ", "مکانی", "حل", "مشکلی", "تمام",
    })

    @classmethod
    def _semantic_terms(cls, value: str) -> set[str]:
        return {
            term for term in DocumentRetrievalService._query_terms(value)
            if term not in cls._FOCUS_STOP and not term.isdecimal()
        }

    @classmethod
    def supports(cls, query: str, segments: tuple, *, heading_terms: tuple[str, ...] = ()) -> bool:
        """Abstain if quoted text has no support for the requested answer slot."""
        text = "\n".join(segment.text for segment in segments)
        terms = cls._semantic_terms(query)
        contextual_text = text + " " + (segments[0].source_location.section or "")
        source_terms = set(DocumentRetrievalService._normalized_tokens(contextual_text)) | set(heading_terms)
        if terms:
            coverage = len(terms & source_terms) / len(terms)
            minimum = 0.30 if (re.search(r"چرا|چگونه|چه\s+مشکلی", query)
                               or cls._CONDITIONAL_TIME.search(query)
                               or re.search(r"(?:دو|سه|چهار)\s+(?:تهدید|عامل|دلیل)", query)) else 0.50
            if coverage < minimum:
                return False
        if cls._IP_QUESTION.search(query) and not cls._IP_FACT.search(text):
            return False
        if cls._IDENTIFIER_QUESTION.search(query) and not cls._IDENTIFIER_FACT.search(text):
            return False
        if cls._MODEL_QUESTION.search(query) and not cls._MODEL_FACT.search(text):
            return False
        if cls._COMPANY_NAME_QUESTION.search(query) and not cls._COMPANY_NAME_FACT.search(text):
            return False
        if cls._DATE_INTENT.search(query) and not cls._DATE_FACT.search(text):
            if not (cls._CONDITIONAL_TIME.search(query) and cls._CONDITION_FACT.search(text)):
                return False
        if re.search(r"(?:نرخ|چند)\s*درصد|چند\s*درصد|درصد\s+بود", query):
            if not cls._PERCENT.search(text):
                return False
        # Require two numbers when comparing an original *amount* to the final amount.
        if (re.search(r"پیشنهاد|پیش\s*نویس|اولیه", query)
                and re.search(r"نهایی|قطعی|مصوب", query)
                and re.search(r"مبلغ|رقم|عدد|اعتبار|هزینه|درآمد", query)):
            figures = [x.group(0).translate(DocumentRetrievalService._CHAR_MAP)
                       for x in cls._NUMERIC.finditer(text)]
            values = {v for v in figures if not (len(v) == 4 and v.isdecimal()
                       and (1300 <= int(v) <= 1499 or 1900 <= int(v) <= 2099))}
            if len(values) < 2:
                return False
        if re.search(r"(?:چند|چقدر|مبلغ|بودجه|درآمد|هزینه|افزایش)\b", query):
            normalized = DocumentRetrievalService._normalized_tokens(text)
            actual = [t for t in normalized if t.isdecimal() and not (
                len(t) == 4 and (1300 <= int(t) <= 1499 or 1900 <= int(t) <= 2099))]
            spelled = set(normalized) & {
                "یک", "دو", "سه", "چهار", "پنج", "شش", "هفت", "هشت", "نه", "ده", "نیم",
            }
            if not actual and not spelled and not cls._CONDITION_FACT.search(text):
                return False
        if re.search(r"(?:دو|سه)\s+(?:تهدید|عامل)", query):
            if (not re.search(r"تهدید|خطا|عامل|سوگیری", text)
                    or not re.search(r"اول|نخست|دوم|ریزش|ناقص", text)):
                return False
        # A heading saying "four criteria" is not evidence of all four items.
        requested = re.search(r"(?:سه|چهار)\s+(?:شرط|معیار|مورد|محور|پرسش|عامل|دلیل)", query)
        if requested:
            n = 4 if requested.group(0).startswith("چهار") else 3
            enumerated = len(set(DocumentRetrievalService._normalized_tokens(text)) & {
                "اول", "دوم", "سوم", "چهارم", "نخست", "ابتدا",
            })
            if enumerated < n and text.count("؟") < n and text.count(";") < n - 1:
                return False
        return True

    @classmethod
    def conflicting_percent_evidence(cls, query: str, chosen: tuple, source: tuple):
        """Abstain on distinct source values for one scoped metric and period.

        Different periods/metrics (e.g. sales versus churn) are not conflicts.
        """
        if (not re.search(r"نرخ|درصد", query)
                or re.search(r"مقایسه|تفاوت\s+دو\s+نرخ", query)
                or not chosen):
            return ()
        anchor = next((s for s in chosen if cls._PERCENT.search(s.text)), None)
        if anchor is None or not anchor.source_location.section:
            return ()
        anchor_values = {
            m.group(1).translate(DocumentRetrievalService._CHAR_MAP).replace("٫", ".")
            for m in cls._PERCENT.finditer(anchor.text)
        }
        if len(anchor_values) != 1:
            return ()
        anchor_years = {
            t for t in DocumentRetrievalService._normalized_tokens(anchor.text)
            if t.isdecimal() and len(t) == 4
        }
        anchor_terms = cls._semantic_terms(query) & set(
            DocumentRetrievalService._normalized_tokens(anchor.text)
        )
        for segment in source:
            if (segment == anchor
                    or segment.source_location.section != anchor.source_location.section):
                continue
            values = {
                m.group(1).translate(DocumentRetrievalService._CHAR_MAP).replace("٫", ".")
                for m in cls._PERCENT.finditer(segment.text)
            }
            if len(values) != 1 or values == anchor_values:
                continue
            candidate_years = {
                t for t in DocumentRetrievalService._normalized_tokens(segment.text)
                if t.isdecimal() and len(t) == 4
            }
            if anchor_years and candidate_years and anchor_years != candidate_years:
                continue
            shared = anchor_terms & set(DocumentRetrievalService._normalized_tokens(segment.text))
            metrics = shared - {
                "نرخ", "درصد", "سال", "دوره", "مهر", "آبان", "آذر",
                "دی", "بهمن", "اسفند", "فروردین", "اردیبهشت", "خرداد",
                "تیر", "مرداد", "شهریور", "قطعی", "واقع", "میزان",
            }
            if (len(shared) >= 2 and metrics
                    and re.search(r"\bهمان\b|\bاما\b|\bمتناقض\b", segment.text)
                    and abs(segment.document_order - anchor.document_order) <= 4):
                return tuple(sorted((anchor, segment), key=lambda s: s.document_order))
        return ()
