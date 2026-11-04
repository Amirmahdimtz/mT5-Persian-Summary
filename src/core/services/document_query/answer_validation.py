"""Conservative evidence checks for extractive Persian document answers.

This pure helper never generates text, accesses external services or receives an
answer key. It may abstain when the requested fact cannot be verified.
"""

from __future__ import annotations

import re
from ipaddress import ip_address

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
    _IDENTIFIER_QUESTION = re.compile(r"(?:شماره|شناسه|کد)\s+([^\W\d_]+)")
    _IDENTIFIER_FACT = re.compile(r"(?:شماره|شناسه|کد)\s*(?:[\w\u0600-\u06ff]{1,20}\s+){0,3}[:：-]?\s*[0-9۰-۹][\w\-/]*")
    _MODEL_QUESTION = re.compile(r"(?:مدل|تیپ)\s+(?:\S+)")
    _MODEL_FACT = re.compile(r"(?:مدل|تیپ)\s*[:：]?\s*[\w\-/]{2,}")
    _COMPANY_NAME_QUESTION = re.compile(r"(?:نام|اسم)\s+(?:(?:شرکت|تأمین[\u200c -]*کننده|تامین[\u200c -]*کننده|سازنده))")
    _COMPANY_NAME_FACT = re.compile(r"(?:شرکت|تأمین[\u200c -]*کننده|تامین[\u200c -]*کننده|سازنده)\s+(?:[\u0600-\u06ff\w-]{2,}\s*){1,3}")
    _CONDITIONAL_TIME = re.compile(r"چه\s+زمانی.*(?:اجازه|ترخیص|مجاز|امکان)|چه\s+شرطی")
    _CONDITION_FACT = re.compile(r"(?:پس\s+از|در\s+صورت|مشروط\s+به|تنها\s+اگر|فقط\s+پس\s+از)")
    _PERCENT = re.compile(r"([0-9۰-۹٠-٩]+(?:[٫.][0-9۰-۹٠-٩]+)?)\s*(?:درصد|[%٪])")
    _MONTH_YEAR = re.compile(
        r"(فروردین|اردیبهشت|خرداد|تیر|مرداد|شهریور|مهر|آبان|آذر|دی|بهمن|اسفند)"
        r"\s+([0-9۰-۹٠-٩]{4})"
    )
    _SUPPLIER = re.compile(r"(?:تأمین|تامین)[\u200c -]*کننده")
    _RATE_MEASURES = frozenset({
        "رشد", "فروش", "ریزش", "خرابی", "خطا", "تورم", "بازده",
        "سود", "درآمد", "پژوهش", "آموزش", "کسری", "کاهش",
        "افزایش", "تولید", "تاخیر", "تأخیر",
    })
    _PRICE_QUERY = re.compile(r"قیمت|بها(?:ی)?|تعرفه")
    _PRICE_CLAIM = re.compile(r"قیمت|بها(?:ی)?|هزینه|تعرفه|نرخ")
    _NUMERIC = re.compile(r"[0-9۰-۹٠-٩][0-9۰-۹٠-٩٬,٫.]*")
    # Month names alone cannot prove a requested calendar date.
    _EXPLICIT_DATE = re.compile(
        r"(?:[0-9۰-۹٠-٩]{1,2}\s+(?:فروردین|اردیبهشت|خرداد|تیر|مرداد|شهریور|مهر|آبان|آذر|دی|بهمن|اسفند|ژانویه|فوریه|مارس|آوریل|مه|ژوئن|ژوئیه|اوت|سپتامبر|اکتبر|نوامبر|دسامبر))"
        r"|(?:[0-9۰-۹٠-٩]{4}[-/][0-9۰-۹٠-٩]{1,2}[-/][0-9۰-۹٠-٩]{1,2})"
        r"|(?:سال(?:\s+مالی)?\s+[0-9۰-۹٠-٩]{4})"
    )
    _MODEL_CODE = re.compile(
        r"[A-Za-z][A-Za-z0-9/_-]*[0-9][A-Za-z0-9/_-]*"
        r"|(?<!\w)[0-9۰-۹٠-٩]{3,}(?!\w)"
    )
    _MISSING_VALUE = re.compile(
        r"نامشخص|مشخص\s+نیست|معلوم\s+نیست"
        r"|(?:اعلام|ثبت|تعیین|ذکر|منتشر)\s+نشده"
        r"|شماره\s+ندارد|در\s+دسترس\s+نیست"
    )
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
    def _identifier_supported(cls, query: str, text: str) -> bool:
        """Require the requested identifier kind, not an unrelated nearby code."""
        requested = cls._IDENTIFIER_QUESTION.search(query)
        if requested is None:
            return True
        label = re.escape(requested.group(1))
        number = r"[0-9۰-۹٠-٩][\w/-]*"
        after_kind = (
            rf"(?:شماره|شناسه|کد)\s+{label}\b"
            rf"(?:\s+[^\W\d_]+){{0,4}}\s*[:：-]?\s*{number}"
        )
        before_kind = (
            rf"{label}\b(?:\s+[^\W\d_]+){{0,4}}\s+"
            rf"(?:به\s+)?(?:شماره|شناسه|کد)\s*[:：-]?\s*{number}"
        )
        return any(
            not cls._MISSING_VALUE.search(match.group(0))
            for pattern in (after_kind, before_kind)
            for match in re.finditer(pattern, text)
        )

    @classmethod
    def _valid_ip_supported(cls, text: str) -> bool:
        """Reject syntactically plausible but invalid IPv4/IPv6 literals."""
        for candidate in cls._IP_FACT.finditer(text):
            try:
                ip_address(candidate.group())
            except ValueError:
                continue
            return True
        return False

    @classmethod
    def _date_supported(cls, query: str, text: str) -> bool:
        """Only accept dates in clauses tied to the requested subject."""
        focus = cls._semantic_terms(query) - {
            "دقیق", "روزی", "تاریخی", "سال", "ماه", "روز", "زمان", "زمانی",
        }
        for clause in re.split(r"[؛\n]|(?<=[.!؟])\s+", text):
            if (cls._EXPLICIT_DATE.search(clause)
                    and (not focus or focus & set(
                        DocumentRetrievalService._normalized_tokens(clause)
                    ))):
                return True
        return False

    @classmethod
    def _model_supported(cls, text: str) -> bool:
        """A model mention requires a code, not an incidental temperature or year."""
        for match in re.finditer(r"مدل|تیپ", text):
            tail = re.split(
                r"[؛\n]|(?<=[.!؟])\s+", text[match.end():], maxsplit=1
            )[0][:100]
            if cls._MISSING_VALUE.search(tail):
                continue
            for code in cls._MODEL_CODE.finditer(tail):
                normalized = code.group().translate(DocumentRetrievalService._CHAR_MAP)
                if (normalized.isdecimal() and len(normalized) == 4
                        and (1300 <= int(normalized) <= 1499
                             or 1900 <= int(normalized) <= 2099)):
                    continue
                return True
        return False

    @classmethod
    def _company_name_supported(cls, query: str, text: str) -> bool:
        """A document owner's company is not proof of a missing supplier name."""
        supplier_query = bool(cls._SUPPLIER.search(query))
        for clause in re.split(r"[؛\n]|(?<=[.!؟])\s+", text):
            if cls._MISSING_VALUE.search(clause):
                continue
            if supplier_query:
                if not cls._SUPPLIER.search(clause):
                    continue
                if re.search(
                    r"(?:تأمین|تامین)[\u200c -]*کننده(?:\s+\S+){0,3}\s+ندارد",
                    clause,
                ):
                    continue
            if cls._COMPANY_NAME_FACT.search(clause):
                return True
        return False

    @classmethod
    def _price_supported(cls, query: str, text: str) -> bool:
        """Do not substitute a project's budget for an asked-for price or fare."""
        requested = cls._semantic_terms(query) - {
            "قیمت", "بها", "بهای", "تعرفه", "نرخ", "هزینه",
        }
        for clause in re.split(r"[؛\n]|(?<=[.!؟])\s+", text):
            if (cls._PRICE_CLAIM.search(clause)
                    and cls._NUMERIC.search(clause)
                    and not cls._MISSING_VALUE.search(clause)
                    and (not requested or requested & set(
                        DocumentRetrievalService._normalized_tokens(clause)
                    ))):
                return True
        return False

    @classmethod
    def _percent_supported(cls, query: str, text: str) -> bool:
        """Bind a percentage to the queried metric within its source clause."""
        focus = cls._semantic_terms(query) - {
            "نرخ", "درصد", "سهم", "میزان", "قطعی", "واقع", "اصلی",
            "سال", "ماه", "دوره", "فروردین", "اردیبهشت", "خرداد",
            "تیر", "مرداد", "شهریور", "مهر", "آبان", "آذر",
            "دی", "بهمن", "اسفند", "ژانویه", "فوریه", "مارس",
            "آوریل", "مه", "ژوئن", "ژوئیه", "اوت", "سپتامبر",
            "اکتبر", "نوامبر", "دسامبر",
        }
        requested_periods = {
            (month, year.translate(DocumentRetrievalService._CHAR_MAP))
            for month, year in cls._MONTH_YEAR.findall(query)
        }
        for clause in re.split(r"[؛\n]|(?<=[.!؟])\s+", text):
            if not cls._PERCENT.search(clause):
                continue
            clause_periods = {
                (month, year.translate(DocumentRetrievalService._CHAR_MAP))
                for month, year in cls._MONTH_YEAR.findall(clause)
            }
            if requested_periods and not requested_periods.issubset(clause_periods):
                continue
            clause_terms = set(DocumentRetrievalService._normalized_tokens(clause))
            measures = (set(DocumentRetrievalService._normalized_tokens(query))
                        & cls._RATE_MEASURES)
            if measures and not measures.issubset(clause_terms):
                continue
            if cls._MISSING_VALUE.search(clause):
                continue
            if not focus or focus & clause_terms:
                return True
        return False

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
        if cls._IP_QUESTION.search(query) and not cls._valid_ip_supported(text):
            return False
        if not cls._identifier_supported(query, text):
            return False
        if cls._MODEL_QUESTION.search(query) and not cls._model_supported(text):
            return False
        if cls._COMPANY_NAME_QUESTION.search(query) and not cls._company_name_supported(query, text):
            return False
        if cls._PRICE_QUERY.search(query) and not cls._price_supported(query, text):
            return False
        if cls._DATE_INTENT.search(query) and not cls._DATE_FACT.search(text):
            if not (cls._CONDITIONAL_TIME.search(query) and cls._CONDITION_FACT.search(text)):
                return False
        if (re.search(r"تاریخ|چه\s+روزی|چه\s+تاریخی", query)
                and not cls._date_supported(query, text)
                and not (cls._CONDITIONAL_TIME.search(query) and cls._CONDITION_FACT.search(text))):
            return False
        if re.search(r"(?:نرخ|چند)\s*درصد|چند\s*درصد|درصد\s+بود", query):
            if not cls._percent_supported(query, text):
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
        if anchor is None:
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
            if segment == anchor:
                continue
            anchor_location, location = anchor.source_location, segment.source_location
            if anchor_location.document_type != location.document_type:
                continue
            if (anchor_location.document_type == "docx"
                    and (not anchor_location.section
                         or anchor_location.section != location.section)):
                continue
            if (anchor_location.document_type == "pdf"
                    and anchor_location.page != location.page):
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
