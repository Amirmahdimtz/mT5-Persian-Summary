"""Answer-validation regressions on synthetic, source-exact Persian documents."""

from __future__ import annotations

import asyncio
from io import BytesIO

import pytest
from docx import Document

from src.core.services.document_query.document_query_service import DocumentQueryService
from src.core.services.summarization.document_extraction_service import DocumentExtractionService
from src.core.services.summarization.document_retrieval_service import DocumentRetrievalService


def _service() -> DocumentQueryService:
    return DocumentQueryService(DocumentRetrievalService(DocumentExtractionService()))


def _ask(text: str, question: str):
    return asyncio.run(_service().query_file_async(text.encode(), "document.txt", question))


def _docx(*sections: tuple[str, list[str]]) -> bytes:
    document = Document()
    for heading, paragraphs in sections:
        document.add_heading(heading, level=1)
        for paragraph in paragraphs:
            document.add_paragraph(paragraph)
    output = BytesIO()
    document.save(output)
    return output.getvalue()


@pytest.mark.parametrize("question,source", [
    ("شماره قرارداد خرید تجهیزات چه بود؟", "بودجه خرید تجهیزات ۶۰۰ میلیون تومان است؛ هنوز قراردادی منتشر نشده است."),
    ("مدل دستگاه کنترل دمای سردخانه چه بود؟", "دستگاه کنترل دما در سردخانه روی عدد ۵ درجه قرار داشت."),
    ("نام شرکت تأمین‌کننده نرم‌افزار درمانگاه چیست؟", "نرم‌افزار درمانگاه در پایلوت چهار مرکز آزمایش شد."),
    ("آدرس IP درگاه سرویس هنگام اختلال چه بود؟", "اختلال درگاه سرویس از ساعت ۱۰:۰۰ تا ۱۰:۲۰ ادامه داشت."),
])
def test_unanswerable_specific_slot_abstains(question, source):
    result = _ask(source, question)
    assert result.status == "not_found"
    assert result.answer is None and result.evidence == ()


@pytest.mark.parametrize("question,source,expected", [
    ("شماره قرارداد خرید تجهیزات چه بود؟", "شماره قرارداد خرید تجهیزات ۷۶۲۳ ثبت شد.", "۷۶۲۳"),
    ("مدل دستگاه کنترل دمای سردخانه چه بود؟", "مدل دستگاه کنترل دما Thermo-A7 است.", "Thermo-A7"),
    ("آدرس IP درگاه سرویس هنگام اختلال چه بود؟", "آدرس IP درگاه سرویس 192.0.2.44 ثبت شده است.", "192.0.2.44"),
])
def test_explicit_specific_slot_is_answerable(question, source, expected):
    result = _ask(source, question)
    assert result.status == "found", result
    assert expected in result.answer
    assert result.answer == "\n".join(e.text for e in result.evidence)


def test_conditional_permission_without_calendar_date():
    text = (
        "انبار موقت کالا آماده است. "
        "ترخیص فقط پس از دو آزمایش مستقل و تأیید کتبی مسئول کنترل کیفیت مجاز خواهد بود."
    )
    result = _ask(text, "کالا چه زمانی اجازه ترخیص دارد؟")
    assert result.status == "found"
    assert "پس از دو آزمایش" in result.answer


def test_multi_paragraph_answer_spans_one_true_docx_heading_only():
    raw = _docx(
        ("[R01] شرایط ادامه آزمایش", [
            "برای ادامه آزمایش چهار شرط لازم است.",
            "شرط اول دسترسی رایگان است.",
            "شرط دوم حفظ داده خصوصی است.",
            "شرط سوم امکان فعالیت آفلاین است.",
            "شرط چهارم آموزش کارکنان است.",
        ]),
        ("[R02] مورد بی‌ارتباط", [
            "طرح دیگری درباره مسکن بدون شرط آزمایش بررسی می‌شود.",
        ]),
    )
    result = asyncio.run(_service().query_file_async(
        raw, "report.docx", "چهار شرط ادامه آزمایش چیست؟"
    ))
    assert result.status == "found", result
    assert all(x in result.answer for x in ("اول", "دوم", "سوم", "چهارم"))
    assert "مسکن" not in result.answer
    assert len(result.answer) <= 1200
    assert result.answer == "\n".join(e.text for e in result.evidence)


def test_unsupported_list_introduction_does_not_count_as_all_items():
    result = _ask(
        "کمیته چهار معیار برای ادامه پروژه مشخص کرده است.",
        "چهار معیار ادامه پروژه چه بودند؟",
    )
    assert result.status == "not_found"


def test_conflicting_rates_for_same_metric_abstain():
    raw = _docx(("[F01] شاخص واحد", [
        "در واحد عملیات، نرخ خرابی تجهیزات در مهر ۱۴۰۴ برابر ۲٫۱ درصد گزارش شد.",
        "اما واحد کنترل کیفیت برای همان تجهیزات در همان مهر ۱۴۰۴ نرخ ۲٫۸ درصد ثبت کرد.",
        "هنوز اختلاف این دو عدد رفع نشده است.",
    ]))
    result = asyncio.run(_service().query_file_async(
        raw, "report.docx", "نرخ قطعی خرابی تجهیزات در مهر ۱۴۰۴ چند درصد بود؟"
    ))
    assert result.status == "ambiguous", result
    assert result.answer is None
    assert len(result.evidence) == 2
    assert "۲٫۱" in result.evidence[0].text
    assert "۲٫۸" in result.evidence[1].text


def test_distinct_metric_rates_are_not_false_conflicts():
    raw = _docx(("[F01] عملکرد تجاری", [
        "نرخ رشد فروش در مهر ۱۴۰۴ برابر ۲٫۱ درصد بود.",
        "اما نرخ ریزش مشتری در همان مهر ۱۴۰۴ برابر ۲٫۸ درصد گزارش شد.",
    ]))
    result = asyncio.run(_service().query_file_async(
        raw, "report.docx", "نرخ رشد فروش در مهر ۱۴۰۴ چند درصد بود؟"
    ))
    assert result.status == "found", result
    assert "۲٫۱" in result.answer


def test_focused_summary_contract_unchanged():
    text = "بودجه توسعه آموزش ۳۰۰ میلیون است.\n\nکارکنان شبکه یک دوره آموزشی دیدند."
    result = asyncio.run(_service().query_file_async(
        text.encode(), "report.txt", "بودجه آموزش", mode="focused_summary"
    ))
    assert result.status == "found"
    assert result.answer == "\n".join(e.text for e in result.evidence)


def test_plain_paragraph_heading_supports_enumerated_answer_without_leaking():
    """DOCX headings can be plain paragraphs, not only Heading-styled text."""
    document = Document()
    document.add_paragraph("[S01] ارزیابی مداخله آموزشی")
    document.add_paragraph("گروه مداخله با گروه مقایسه ارزیابی شد.")
    document.add_paragraph("[S02] تهدیدهای اعتبار نتیجه")
    document.add_paragraph(
        "سه خطای تحلیلی نتیجه ارزیابی را مخدوش می‌کنند: "
        "اول سوگیری انتخاب، دوم ریزش نمونه و سوم تغییر معیار."
    )
    output = BytesIO()
    document.save(output)
    result = asyncio.run(_service().query_file_async(
        output.getvalue(), "study.docx",
        "دو تهدید اعتبار ارزیابی مداخله آموزشی چیست؟",
    ))
    assert result.status == "found"
    assert "سوگیری انتخاب" in result.answer and "ریزش نمونه" in result.answer
    assert "گروه مقایسه" not in result.answer
    assert result.answer == "\n".join(e.text for e in result.evidence)


@pytest.mark.parametrize("question,source", [
    (
        "شماره قرارداد خرید تجهیزات چه بود؟",
        "شماره پرونده خرید تجهیزات ۷۶۲۳ ثبت شد. قرارداد خرید هنوز شماره ندارد.",
    ),
    (
        "مدل دستگاه کنترل دما چه بود؟",
        "مدل دستگاه کنترل دما نامشخص است؛ دمای آن ۵۰ درجه است.",
    ),
    (
        "آدرس IP درگاه سرویس چیست؟",
        "آدرس IP درگاه سرویس 999.999.999.999 ثبت شد.",
    ),
    (
        "تاریخ جلسه بعدی چه بود؟",
        "تاریخ جلسه بعدی در ماه آبان بررسی شد اما روز آن مشخص نیست.",
    ),
    (
        "نرخ رشد فروش چند درصد بود؟",
        "نرخ رشد فروش اعلام نشد؛ نرخ ریزش مشتری ۳ درصد بود.",
    ),
    (
        "نرخ رشد فروش در مهر ۱۴۰۴ چند درصد بود؟",
        "نرخ رشد فروش در مهر ۱۴۰۴ اعلام نشد؛ نرخ ریزش مشتری در همان مهر ۱۴۰۴ برابر ۳ درصد بود.",
    ),
    (
        "تاریخ جلسه بعدی چه بود؟",
        "تاریخ جلسه بعدی اعلام نشده است؛ نمایشگاه در ۱۴ آبان ۱۴۰۵ افتتاح می‌شود.",
    ),
    (
        "شماره قرارداد خرید تجهیزات چه بود؟",
        "شماره قرارداد مشخص نیست و جلسه ۷۶۲۳ ثبت شد.",
    ),
])
def test_unrelated_or_unverified_slots_do_not_create_answers(question, source):
    result = _ask(source, question)
    assert result.status == "not_found", result
    assert result.answer is None
    assert result.evidence == ()


def test_requested_identifier_can_precede_numeric_reference():
    result = _ask(
        "قرارداد خرید تجهیزات به شماره ۷۶۲۳ ثبت شد.",
        "شماره قرارداد خرید تجهیزات چه بود؟",
    )
    assert result.status == "found", result
    assert "۷۶۲۳" in result.answer
    assert result.answer == "\n".join(item.text for item in result.evidence)


def test_requested_percentage_metric_remains_answerable():
    result = _ask(
        "نرخ رشد فروش در مهر ۱۴۰۴ برابر ۲٫۱ درصد بود.",
        "نرخ رشد فروش در مهر ۱۴۰۴ چند درصد بود؟",
    )
    assert result.status == "found", result
    assert "۲٫۱ درصد" in result.answer
