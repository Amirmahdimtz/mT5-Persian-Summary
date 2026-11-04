"""Stage 12 extractive-only source grounding, field validation and HTTP safety."""

from __future__ import annotations

import asyncio
from io import BytesIO

import pytest
from docx import Document
from fastapi.testclient import TestClient

from src.core.services.document_query.document_query_service import (
    DocumentQueryInputError, DocumentQueryService,
)
from src.core.services.summarization.document_extraction_service import DocumentExtractionService
from src.core.services.summarization.document_retrieval_service import DocumentRetrievalService
from src.application.document_query.dtos.document_query_dto import DocumentQueryResponseDto


def _service() -> DocumentQueryService:
    return DocumentQueryService(DocumentRetrievalService(DocumentExtractionService()))


def _docx(*paragraphs: str) -> bytes:
    doc = Document()
    for paragraph in paragraphs:
        doc.add_paragraph(paragraph)
    output = BytesIO()
    doc.save(output)
    return output.getvalue()


@pytest.mark.parametrize("question,expected", [
    ("تاریخ جلسه بعدی چه زمانی است؟", "۱۴ آبان ۱۴۰۵"),
    ("چه کسی مسئول پیگیری است؟", "آقای رضایی"),
    ("بودجه اولیه پروژه چقدر است؟", "۳۵۰ میلیون"),
])
def test_stage12_answer_contains_exact_relevant_source_fact(question, expected):
    content = (
        "جلسه بعدی در تاریخ ۱۴ آبان ۱۴۰۵ برگزار می‌شود.\n\n"
        "آقای رضایی مسئول پیگیری است.\n\n"
        "بودجه اولیه پروژه ۳۵۰ میلیون تومان تعیین شد."
    ).encode()
    result = asyncio.run(_service().query_file_async(content, "report.txt", question))
    assert result.status == "found"
    assert expected in result.answer
    assert result.answer == result.evidence[0].text
    assert result.evidence[0].source_location.paragraph in (1, 2, 3)


def test_stage12_ambiguous_dates_has_no_guess_and_returns_conflicting_evidence():
    content = "تاریخ جلسه بعدی ۱۴ آبان ۱۴۰۵ است.\n\nتاریخ جلسه بعدی ۱۵ آبان ۱۴۰۵ است.".encode()
    result = asyncio.run(_service().query_file_async(content, "report.txt", "تاریخ جلسه بعدی"))
    assert result.status == "ambiguous"
    assert result.answer is None
    assert len(result.evidence) >= 2
    assert "۱۴ آبان" in result.evidence[0].text
    assert "۱۵ آبان" in result.evidence[1].text


def test_stage12_ambiguous_names_has_no_guess():
    data = "مسئول پیگیری آقای رضایی است.\n\nمسئول پیگیری خانم احمدی است.".encode()
    result = asyncio.run(_service().query_file_async(data, "a.txt", "مسئول پیگیری"))
    assert result.status == "ambiguous" and result.answer is None
    assert len(result.evidence) == 2


def test_stage12_not_found_does_not_return_unrelated_facts():
    data = "در جلسه مربوط به بودجه، مبلغ ۳۵۰ میلیون تومان ثبت شد.".encode()
    result = asyncio.run(_service().query_file_async(data, "a.txt", "تاریخ جلسه بعدی"))
    assert result.status == "not_found"
    assert result.answer is None and result.evidence == ()


def test_stage12_focused_summary_is_cited_topic_excerpts_only():
    content = (
        "در حوزه سلامت دو درمانگاه جدید افتتاح شد.\n\n"
        "دانشگاه‌ها آزمایشگاه هوش مصنوعی راه‌اندازی کردند.\n\n"
        "درمانگاه‌ها در محله‌های محروم فعالیت می‌کنند."
    ).encode()
    result = asyncio.run(_service().query_file_async(
        content, "a.txt", "درمانگاه", mode="focused_summary", summary_length="long"
    ))
    assert result.status == "found"
    assert "آزمایشگاه" not in result.answer
    assert result.answer == "\n".join(e.text for e in result.evidence)
    assert all(e.text in content.decode() for e in result.evidence)


def test_stage12_focused_summary_lengths_are_bounded():
    text = ("گزارش شبکه درباره امنیت سامانه و دسترسی اطلاعات تهیه شد.\n\n" * 15).encode()
    results = {tier: asyncio.run(_service().query_file_async(
        text, "a.txt", "امنیت سامانه", mode="focused_summary", summary_length=tier
    )) for tier in ("short", "medium", "long")}
    assert len(results["short"].answer) <= 320
    assert len(results["medium"].answer) <= 680
    assert len(results["long"].answer) <= 1200
    assert all(r.status == "found" for r in results.values())


def test_stage12_docx_has_true_paragraph_and_no_page():
    raw = _docx("گزارش وضعیت شبکه آماده شد.", "آقای رضایی مسئول پیگیری است.")
    result = asyncio.run(_service().query_file_async(raw, "a.docx", "مسئول پیگیری"))
    assert result.status == "found"
    assert result.evidence[0].source_location.page is None
    assert result.evidence[0].source_location.paragraph == 2


@pytest.mark.parametrize("mode,length", [
    ("answer", "short"), ("answer", "long"), ("invalid", None),
    ("focused_summary", "tiny"),
])
def test_stage12_rejects_invalid_mode_length_before_file_parsing(mode, length):
    with pytest.raises(DocumentQueryInputError):
        asyncio.run(_service().query_file_async(
            b"not a PDF", "a.pdf", "بودجه اولیه", mode=mode, summary_length=length
        ))


@pytest.fixture
def http():
    # Exercise real controller discovery, ConfigReader and ASGI upload guards.
    from src.host.app import app

    with TestClient(app) as client:
        yield client


def _post(http, data=None, content=None, filename="report.txt", mime="text/plain"):
    return http.post(
        "/api/v1/document_query/file",
        files={"file": (filename, content or "بودجه اولیه پروژه ۳۵۰ میلیون تومان است.".encode(), mime)},
        data=data if data is not None else {"query": "بودجه اولیه پروژه چقدر است؟"},
    )


def test_stage12_http_answer_and_swagger(http):
    paths = http.get("/openapi.json").json()["paths"]
    assert "/api/v1/document_query/file" in paths
    assert "/api/v1/summarization/text" in paths
    response = _post(http)
    assert response.status_code == 200, response.text
    data = DocumentQueryResponseDto.model_validate(response.json())
    assert data.status == "found" and data.mode == "answer"
    assert "۳۵۰" in data.answer
    assert data.evidence[0].paragraph == 1
    assert data.evidence[0].location_type == "paragraph"


def test_stage12_http_focused_summary(http):
    r = _post(http, data={
        "query": "بودجه اولیه پروژه", "mode": "focused_summary", "summary_length": "short"
    })
    assert r.status_code == 200 and r.json()["status"] == "found"
    assert r.json()["answer"] == r.json()["evidence"][0]["text"]


@pytest.mark.parametrize("data", [
    {}, {"query": " "}, {"query": "x" * 513}, {"query": "و به در"},
    {"query": "بودجه اولیه", "mode": "unknown"},
    {"query": "بودجه اولیه", "summary_length": "short"},
    {"query": "بودجه اولیه", "mode": "focused_summary", "summary_length": "tiny"},
    {"query": "بودجه اولیه", "extra": "PRIVATE"},
])
def test_stage12_http_validation_rejects_unsafe_form(http, data):
    r = _post(http, data=data)
    assert r.status_code == 422, r.text
    assert "PRIVATE" not in r.text


def test_stage12_http_repeated_query_rejected(http):
    # Encode repeated fields as a genuine multipart body, so ASGI upload
    # middleware admits the request and the controller rejects duplicates.
    r = http.post(
        "/api/v1/document_query/file",
        files=[
            ("file", ("a.txt", b"report", "text/plain")),
            ("query", (None, "بودجه")),
            ("query", (None, "هزینه")),
        ],
    )
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "InvalidFormFields"


@pytest.mark.parametrize("filename,mime,status", [
    ("../private.txt", "text/plain", 400),
    ("a.exe", "application/octet-stream", 415),
    ("a.pdf", "text/plain", 415),
])
def test_stage12_http_upload_metadata_is_guarded(http, filename, mime, status):
    r = _post(http, filename=filename, mime=mime)
    assert r.status_code == status


def test_stage12_http_invalid_document_redacted(http):
    r = _post(http, filename="a.pdf", mime="application/pdf", content=b"private raw bytes")
    assert r.status_code == 422
    assert "private raw bytes" not in r.text


def test_stage12_http_no_answers_for_notfound(http):
    r = _post(http, data={"query": "واکسن کودکان"})
    assert r.status_code == 200
    assert r.json()["status"] == "not_found"
    assert r.json()["answer"] is None and r.json()["evidence"] == []


def test_stage12_pdf_location_dto_uses_true_page_not_paragraph():
    from src.application.document_query.document_query_controller import _to_response
    from src.core.services.document_query.document_query_service import (
        DocumentQueryResult, SourceEvidence,
    )
    from src.core.services.summarization.document_extraction_service import SourceLocation
    quote = "تاریخ جلسه در ۱۴ آبان ۱۴۰۵ ثبت شد."
    result = DocumentQueryResult(
        "found", "answer", "تاریخ جلسه", quote,
        (SourceEvidence(quote, SourceLocation("pdf", page=3), 7),),
    )
    dto = _to_response(result)
    assert dto.evidence[0].page == 3
    assert dto.evidence[0].paragraph is None
    assert dto.evidence[0].location_type == "page"
    assert dto.evidence[0].document_order == 7


def test_stage12_http_mapper_rejects_ungrounded_answer():
    from fastapi import HTTPException
    from src.application.document_query.document_query_controller import _to_response
    from src.core.services.document_query.document_query_service import (
        DocumentQueryResult, SourceEvidence,
    )
    from src.core.services.summarization.document_extraction_service import SourceLocation
    value = DocumentQueryResult(
        "found", "answer", "بودجه اولیه", "پاسخ ساختگی ۹۹ میلیون تومان است.",
        (SourceEvidence("بودجه اولیه ۳۵۰ میلیون تومان است.", SourceLocation("txt", paragraph=1), 0),),
    )
    with pytest.raises(HTTPException) as error:
        _to_response(value)
    assert error.value.status_code == 500
    assert "۹۹" not in str(error.value.detail)

def test_relevance_long_question_prefers_requested_amount():
    raw = (
        "افزایش خالص ظرفیت برق در سال ۲۰۲۳ برابر با ۴۷۳ گیگاوات بود. "
        "این رقم ظرفیت نصب‌شده است و نه انرژی تولیدشده.\n\n"
        "سهم یک منطقه از افزایش خالص ظرفیت برق سال ۲۰۲۳ حدود ۶۹ درصد اعلام شد."
    ).encode()
    result = asyncio.run(_service().query_file_async(
        raw, "report.txt", "افزایش خالص ظرفیت برق در سال ۲۰۲۳ چقدر بود و واحد آن چیست؟"
    ))
    assert result.status == "found"
    assert "۴۷۳ گیگاوات" in result.answer
    assert "۶۹ درصد" not in result.answer
    assert result.answer == "\n".join(e.text for e in result.evidence)


def test_relevance_two_part_question_preserves_both_source_excerpts():
    raw = "محور اول جلسه، آموزش معلمان بود. محور دوم جلسه، تأمین تجهیزات مدارس بود.".encode()
    result = asyncio.run(_service().query_file_async(raw, "report.txt", "دو محور جلسه چه بودند؟"))
    assert result.status == "found"
    assert "آموزش معلمان" in result.answer
    assert "تأمین تجهیزات مدارس" in result.answer
    assert len(result.evidence) == 2
    assert result.answer == "\n".join(e.text for e in result.evidence)


def test_relevance_textual_gregorian_date_is_supported():
    raw = "سال مالی شرکت در ۳۰ ژوئن ۲۰۲۴ پایان یافت.".encode()
    result = asyncio.run(_service().query_file_async(raw, "report.txt", "سال مالی در چه تاریخی پایان یافت؟"))
    assert result.status == "found"
    assert "۳۰ ژوئن ۲۰۲۴" in result.answer


def test_relevance_persian_plural_normalization_does_not_change_quote():
    raw = "درمانگاه‌ها در مناطق کم‌برخوردار افتتاح شدند.".encode()
    result = asyncio.run(_service().query_file_async(
        raw, "report.txt", "درمانگاه در کدام مناطق افتتاح شد؟"
    ))
    assert result.status == "found"
    assert "درمانگاه‌ها" in result.answer
    assert result.evidence[0].text in raw.decode()


def test_relevance_no_numeric_answer_abstains_from_nearby_budget():
    raw = (
        "قرارداد شرکت آفتاب امضا شد اما مبلغ آن در گزارش ذکر نشده است.\n\n"
        "بودجه تعمیر تجهیزات آزمایشگاه ۸۰۰ میلیون تومان تعیین شد."
    ).encode()
    result = asyncio.run(_service().query_file_async(
        raw, "report.txt", "مبلغ قرارداد شرکت آفتاب چقدر است؟"
    ))
    assert result.status == "not_found"
    assert result.answer is None and not result.evidence


def test_relevance_unrelated_topic_still_abstains():
    raw = "سود شرکت ۲۰ درصد رشد کرد.".encode()
    result = asyncio.run(_service().query_file_async(
        raw, "report.txt", "واکسن کودکان در کدام شهر توزیع شد؟"
    ))
    assert result.status == "not_found"
    assert result.answer is None and not result.evidence


def test_relevance_conflicting_dates_remain_ambiguous():
    raw = "تاریخ جلسه بعدی ۱۴ آبان ۱۴۰۵ است.\n\nتاریخ جلسه بعدی ۱۵ آبان ۱۴۰۵ است.".encode()
    result = asyncio.run(_service().query_file_async(raw, "report.txt", "تاریخ جلسه بعدی"))
    assert result.status == "ambiguous"
    assert result.answer is None
    assert len(result.evidence) >= 2


def test_relevance_focused_summary_remains_bounded_and_source_exact():
    raw = (
        "بودجه آموزش معلمان در سال جدید افزایش یافت.\n\n"
        "بودجه توسعه مراکز درمانی بدون تغییر ماند.\n\n"
        "آموزش معلمان در پنج استان اجرا می‌شود."
    ).encode()
    result = asyncio.run(_service().query_file_async(
        raw, "report.txt", "آموزش معلمان", mode="focused_summary"
    ))
    assert result.status == "found"
    assert result.answer == "\n".join(e.text for e in result.evidence)
    assert len(result.answer) <= 680
    assert "مراکز درمانی" not in result.answer

