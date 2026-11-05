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


@pytest.mark.parametrize("question,source", [
    (
        "نام شرکت تأمین‌کننده تجهیزات شرکت باران چیست؟",
        "نام شرکت تأمین‌کننده تجهیزات شرکت باران هنوز اعلام نشده است. "
        "بودجه تجهیزات شرکت باران ۴۰۰ میلیون تومان بود.",
    ),
    (
        "نرخ رشد فروش شرکت باران در دی ۱۴۰۴ چند درصد بود؟",
        "نرخ رشد فروش شرکت باران در آذر ۱۴۰۴ برابر ۱۲ درصد بود. "
        "نرخ ریزش مشتری شرکت باران در آذر ۱۴۰۴ برابر ۳ درصد بود.",
    ),
    (
        "قیمت بلیت قطار مسیر ساحلی چقدر است؟",
        "قطار مسیر ساحلی آغاز به کار کرد. "
        "بودجه ساخت مسیر ساحلی ۲۴۰ میلیارد تومان بود. "
        "تعداد مسافران مسیر ساحلی ۱۸ هزار نفر است.",
    ),
    (
        "نرخ رشد فروش شرکت باران در دی ۱۴۰۴ چند درصد بود؟",
        "نرخ ریزش مشتری شرکت باران در دی ۱۴۰۴ برابر ۳ درصد بود.",
    ),
])
def test_scoped_supplier_period_price_and_metric_are_not_inferred(question, source):
    result = _ask(source, question)
    assert result.status == "not_found", result
    assert result.answer is None and result.evidence == ()


@pytest.mark.parametrize("question,source,expected", [
    (
        "نام شرکت تأمین‌کننده تجهیزات شرکت باران چیست؟",
        "شرکت سپهر به عنوان تأمین‌کننده تجهیزات شرکت باران معرفی شد.",
        "شرکت سپهر",
    ),
    (
        "نرخ رشد فروش شرکت باران در دی ۱۴۰۴ چند درصد بود؟",
        "نرخ رشد فروش شرکت باران در دی ۱۴۰۴ برابر ۱۹ درصد بود.",
        "۱۹ درصد",
    ),
    (
        "قیمت بلیت قطار مسیر ساحلی چقدر است؟",
        "قیمت بلیت قطار مسیر ساحلی ۹۰ هزار تومان تعیین شد.",
        "۹۰ هزار تومان",
    ),
])
def test_scoped_positive_answers_remain_source_exact(question, source, expected):
    result = _ask(source, question)
    assert result.status == "found", result
    assert expected in result.answer
    assert result.answer == "\n".join(item.text for item in result.evidence)


def test_conflicting_percentage_in_separate_txt_paragraphs_is_ambiguous():
    source = (
        "در واحد عملیاتی نرخ خرابی تجهیزات در مهر ۱۴۰۴ برابر ۲٫۱ درصد ثبت شد.\n\n"
        "اما واحد کنترل کیفیت برای همان تجهیزات در همان مهر ۱۴۰۴ نرخ ۲٫۸ درصد ثبت کرد."
    )
    result = _ask(source, "نرخ قطعی خرابی تجهیزات در مهر ۱۴۰۴ چند درصد بود؟")
    assert result.status == "ambiguous", result
    assert result.answer is None
    assert len(result.evidence) == 2
    assert "۲٫۱ درصد" in result.evidence[0].text
    assert "۲٫۸ درصد" in result.evidence[1].text


def test_distinct_percentage_metrics_in_txt_are_not_conflicts():
    source = (
        "نرخ رشد فروش شرکت سپهر در مهر ۱۴۰۴ برابر ۲٫۱ درصد بود.\n\n"
        "اما نرخ ریزش مشتری شرکت سپهر در مهر ۱۴۰۴ برابر ۲٫۸ درصد بود."
    )
    result = _ask(source, "نرخ رشد فروش شرکت سپهر در مهر ۱۴۰۴ چند درصد بود؟")
    assert result.status == "found", result
    assert "۲٫۱ درصد" in result.answer
    assert "۲٫۸ درصد" not in result.answer


def test_explicit_two_year_revenue_claims_span_separate_txt_paragraphs():
    source = (
        "درآمد کل شرکت سپهر در سال مالی ۲۰۲۵ برابر ۹۰ میلیارد تومان بود.\n\n"
        "درآمد کل شرکت سپهر در سال مالی ۲۰۲۴ برابر ۷۰ میلیارد تومان بود.\n\n"
        "سود عملیاتی شرکت سپهر در سال مالی ۲۰۲۵ برابر ۱۰ میلیارد تومان بود."
    )
    result = _ask(source, "درآمد کل شرکت سپهر در ۲۰۲۵ و ۲۰۲۴ چقدر بود؟")
    assert result.status == "found", result
    assert "۲۰۲۵ برابر ۹۰ میلیارد تومان" in result.answer
    assert "۲۰۲۴ برابر ۷۰ میلیارد تومان" in result.answer
    assert "سود عملیاتی" not in result.answer
    assert len(result.answer) <= 1200
    assert [item.source_location.paragraph for item in result.evidence] == [1, 2]
    assert result.answer == "\n".join(item.text for item in result.evidence)


def test_two_year_revenue_query_refuses_when_one_year_missing():
    source = (
        "درآمد کل شرکت سپهر در سال مالی ۲۰۲۵ برابر ۹۰ میلیارد تومان بود.\n\n"
        "سود عملیاتی شرکت سپهر در سال مالی ۲۰۲۴ برابر ۱۰ میلیارد تومان بود."
    )
    result = _ask(source, "درآمد کل شرکت سپهر در ۲۰۲۵ و ۲۰۲۴ چقدر بود؟")
    assert result.status == "not_found", result
    assert result.answer is None and result.evidence == ()


@pytest.mark.parametrize("question,source,first,second", [
    (
        "زمان قطعی تحویل تجهیزات پایانه چه تاریخی بود؟",
        "زمان تحویل تجهیزات پایانه ۱۴ مهر ۱۴۰۵ اعلام شد.\n\n"
        "اما در پیوست همان اطلاعیه، زمان تحویل همان تجهیزات ۱۶ مهر ۱۴۰۵ ذکر شد.",
        "۱۴ مهر ۱۴۰۵", "۱۶ مهر ۱۴۰۵",
    ),
    (
        "بودجه قطعی تکمیلی پل شرقی چند میلیون تومان بود؟",
        "بودجه تکمیلی پل شرقی ۶۸۰ میلیون تومان ثبت شد.\n\n"
        "اما گروه حسابرسی بودجه تکمیلی همان پل را ۷۴۰ میلیون تومان اعلام کرد.",
        "۶۸۰ میلیون", "۷۴۰ میلیون",
    ),
    (
        "مسئول قطعی تحویل مسیر گردشگری چه کسی بود؟",
        "مسئول تحویل مسیر گردشگری خانم نازنین امینی معرفی شد.\n\n"
        "اما پیوست همان صورتجلسه مسئول تحویل مسیر را آقای سهراب بهمنی معرفی کرد.",
        "نازنین امینی", "سهراب بهمنی",
    ),
    (
        "ظرفیت قطعی نهایی سالن اسکان چند نفر بود؟",
        "ظرفیت نهایی سالن اسکان ۱۲۰ نفر اعلام شد.\n\n"
        "اما نسخه دوم همان برنامه ظرفیت نهایی اسکان ۱۵۰ نفر را ثبت کرد.",
        "۱۲۰ نفر", "۱۵۰ نفر",
    ),
    (
        "نرخ قطعی بازچرخانی آب کارخانه در مرداد ۱۴۰۵ چند درصد بود؟",
        "نرخ بازچرخانی آب کارخانه در مرداد ۱۴۰۵ برابر ۶۲ درصد بود.\n\n"
        "اما گروه ارزیابی برای همان کارخانه در همان مرداد ۱۴۰۵ نرخ بازچرخانی ۵۸ درصد ثبت کرد.",
        "۶۲ درصد", "۵۸ درصد",
    ),
])
def test_explicit_adjacent_same_claim_conflicts_abstain(question, source, first, second):
    result = _ask(source, question)
    assert result.status == "ambiguous", result
    assert result.answer is None
    assert len(result.evidence) == 2
    assert first in result.evidence[0].text
    assert second in result.evidence[1].text
    assert all(x.source_location.document_type == "txt" for x in result.evidence)


def test_docx_unstyled_paragraphs_conflicting_date_are_not_answered():
    source = _docx(("پرونده برنامه آموزشی", [
        "تاریخ آغاز ثبت نام جدید ۱۷ مهر ۱۴۰۴ اعلام شد.",
        "اما در پیوست همان برنامه تاریخ آغاز ثبت نام جدید ۱۹ مهر ۱۴۰۴ اعلام شد.",
    ]))
    result = asyncio.run(_service().query_file_async(
        source, "notice.docx", "تاریخ قطعی آغاز ثبت نام جدید چه روزی بود؟"
    ))
    assert result.status == "ambiguous", result
    assert result.answer is None
    assert len(result.evidence) >= 2
    assert all(e.source_location.document_type == "docx" for e in result.evidence)


def test_exact_funding_subject_required_instead_of_nearby_meeting_date():
    source = (
        "جلسه طرح توسعه آب‌رسانی دشت لاله در ۳ اردیبهشت ۱۴۰۵ برگزار شد.\n\n"
        "اعتبار مصوب طرح توسعه آب‌رسانی دشت لاله برابر ۱۳۵۰ میلیون تومان تعیین شد."
    )
    result = _ask(source, "اعتبار مصوب طرح توسعه آب‌رسانی دشت لاله چقدر تعیین شد؟")
    assert result.status == "found", result
    assert "۱۳۵۰ میلیون تومان" in result.answer
    assert "جلسه" not in result.answer


def test_amount_question_refuses_calendar_date_as_only_number():
    result = _ask(
        "جلسه طرح تعمیر شبکه آب در ۳ اردیبهشت ۱۴۰۵ برگزار شد.",
        "اعتبار مصوب طرح تعمیر شبکه آب چقدر تعیین شد؟",
    )
    assert result.status == "not_found"
    assert result.answer is None


def test_project_title_increase_is_not_person_quantity_intent():
    result = _ask(
        "مسئول پیگیری اجرای طرح افزایش سرویس روستایی آقای پوریا اعتمادی تعیین شد.",
        "چه کسی مسئول پیگیری اجرای طرح افزایش سرویس روستایی بود؟",
    )
    assert result.status == "found", result
    assert "آقای پوریا اعتمادی" in result.answer


def test_claim_conflict_requires_same_role_and_same_year():
    role = _ask(
        "مسئول پیگیری پروژه گردشگری خانم مینا عباسی بود.\n\n"
        "اما مسئول تحویل پروژه گردشگری آقای نیما نوری تعیین شد.",
        "مسئول پیگیری پروژه گردشگری چه کسی بود؟",
    )
    assert role.status == "found", role
    assert "مینا عباسی" in role.answer
    year = _ask(
        "بودجه تکمیلی پل غربی در سال ۱۴۰۴ برابر ۶۸۰ میلیون تومان بود.\n\n"
        "اما بودجه تکمیلی همان پل در سال ۱۴۰۵ برابر ۷۴۰ میلیون تومان بود.",
        "بودجه تکمیلی پل غربی در سال ۱۴۰۴ چقدر بود؟",
    )
    assert year.status == "found", year
    assert "۶۸۰ میلیون" in year.answer


def test_pdf_page_local_conflict_uses_original_location():
    from src.core.services.document_query.answer_validation import DocumentAnswerValidator
    from src.core.services.summarization.document_extraction_service import (
        DocumentSegment, SourceLocation,
    )

    first = DocumentSegment(
        "تاریخ تحویل نتایج آزمایشگاه خاک ۲۳ مهر ۱۴۰۴ ثبت شد.",
        SourceLocation("pdf", page=2), 0,
    )
    second = DocumentSegment(
        "اما پیوست همان گزارش، تاریخ تحویل همان نتایج آزمایشگاه را ۲۵ مهر ۱۴۰۴ اعلام کرد.",
        SourceLocation("pdf", page=2), 1,
    )
    query = "تاریخ قطعی تحویل نتایج آزمایشگاه خاک چه روزی بود؟"
    assert DocumentAnswerValidator.conflicting_claim_evidence(
        query, (first,), (first, second)
    ) == (first, second)
    other_page = DocumentSegment(second.text, SourceLocation("pdf", page=3), 1)
    assert DocumentAnswerValidator.conflicting_claim_evidence(
        query, (first,), (first, other_page)
    ) == ()


def test_approved_credit_four_digit_amount_in_docx_is_not_a_year():
    source = _docx(("[C01] اعتبار طرح خدمات شهری", [
        "جلسه بررسی طرح ارتقای شبکه شهری در ۳ اردیبهشت ۱۴۰۵ برگزار شد.",
        "اعتبار مصوب طرح ارتقای شبکه شهری برابر ۱۳۵۰ میلیون تومان تعیین شد.",
    ]))
    result = asyncio.run(_service().query_file_async(
        source, "funding.docx",
        "اعتبار مصوب طرح ارتقای شبکه شهری چقدر تعیین شد؟",
    ))
    assert result.status == "found", result
    assert "۱۳۵۰ میلیون تومان" in result.answer
    assert "جلسه" not in result.answer
    assert result.answer == "\n".join(item.text for item in result.evidence)


def test_approved_credit_requires_money_not_just_a_fiscal_year():
    result = _ask(
        "گزارش اعتبار مصوب طرح نگهداری پل در سال ۱۳۵۰ تهیه شد.",
        "اعتبار مصوب طرح نگهداری پل چقدر بود؟",
    )
    assert result.status == "not_found", result
    assert result.answer is None
