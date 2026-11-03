"""Stage 11 structured source locations and offline retrieval regression tests."""

from __future__ import annotations

import asyncio
from io import BytesIO

import pytest
from docx import Document
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from benchmarks.stage11_retrieval_benchmark import evaluate
from src.core.services.summarization.document_extraction_service import (
    DocumentExtractionService, DocumentLimitError, DocumentSegment,
    InvalidTextEncodingError, NoExtractableTextError, SourceLocation,
)
from src.core.services.summarization.document_retrieval_service import (
    DocumentRetrievalService, RetrievalInputError,
)
from src.infrastructure.di.bootstrap import bootstrap_di
from src.infrastructure.di.inject import resolve


def _pdf_with_text(*pages: str) -> bytes:
    writer = PdfWriter()
    for text in pages:
        page = writer.add_blank_page(width=612, height=792)
        if not text:
            continue
        unique = list(dict.fromkeys(text))
        mapping = {char: index + 1 for index, char in enumerate(unique)}
        codepoints = "\n".join(
            f"<{index:02X}> <{ord(char):04X}>" for char, index in mapping.items()
        )
        cmap = (
            "/CIDInit /ProcSet findresource begin\n12 dict begin\nbegincmap\n"
            "/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def\n"
            "/CMapName /Adobe-Identity-UCS def\n/CMapType 2 def\n"
            "1 begincodespacerange\n<00> <FF>\nendcodespacerange\n"
            f"{len(mapping)} beginbfchar\n{codepoints}\nendbfchar\n"
            "endcmap\nCMapName currentdict /CMap defineresource pop\nend\nend"
        )
        cmap_stream = DecodedStreamObject()
        cmap_stream.set_data(cmap.encode("ascii"))
        font = DictionaryObject({
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
            NameObject("/Encoding"): NameObject("/WinAnsiEncoding"),
            NameObject("/ToUnicode"): writer._add_object(cmap_stream),
        })
        page[NameObject("/Resources")] = DictionaryObject({
            NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})
        })
        stream = DecodedStreamObject()
        stream.set_data(("BT /F1 12 Tf 50 700 Td <" +
                         "".join(f"{mapping[ch]:02X}" for ch in text) +
                         "> Tj ET").encode("ascii"))
        page[NameObject("/Contents")] = writer._add_object(stream)
    result = BytesIO()
    writer.write(result)
    return result.getvalue()


def _docx_with_table() -> bytes:
    doc = Document()
    doc.add_heading("فصل اول", level=1)
    doc.add_paragraph("آقای رضایی مسئول بررسی امنیت سامانه است.")
    table = doc.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "نام"
    table.cell(0, 1).text = "وظیفه"
    table.cell(1, 0).text = "احمدی"
    table.cell(1, 1).text = "گزارش هزینه‌ها"
    doc.add_paragraph("جلسه در ۱۴ آبان ۱۴۰۵ برگزار شد.")
    result = BytesIO()
    doc.save(result)
    return result.getvalue()


def test_stage11_txt_paragraph_locations_and_preserved_unicode():
    extractor = DocumentExtractionService()
    source = "جلسه اول در ۱۴ آبان برگزار شد.\n\nمبلغ ۳۵۰ میلیون تومان تعیین شد.\n"
    data = source.encode("utf-8")
    segments = extractor.extract_segments(data, "report.TXT")
    assert [s.text for s in segments] == [
        "جلسه اول در ۱۴ آبان برگزار شد.", "مبلغ ۳۵۰ میلیون تومان تعیین شد.",
    ]
    assert [s.source_location.paragraph for s in segments] == [1, 2]
    assert [s.document_order for s in segments] == [0, 1]
    assert all(s.source_location.page is None for s in segments)
    assert extractor.extract(data, "report.TXT") == source.strip()


def test_stage11_pdf_page_numbers_include_blank_pages():
    extractor = DocumentExtractionService()
    raw = _pdf_with_text("صفحه اول فارسی.", "", "صفحه سوم فارسی.")
    segments = extractor.extract_segments(raw, "file.pdf")
    assert [s.source_location.page for s in segments] == [1, 3]
    assert [s.text for s in segments] == ["صفحه اول فارسی.", "صفحه سوم فارسی."]
    assert all(s.source_location.paragraph is None for s in segments)
    assert extractor.extract(raw, "file.pdf") == "صفحه اول فارسی.\n\nصفحه سوم فارسی."


def test_stage11_docx_true_paragraph_table_and_section_locations():
    extractor = DocumentExtractionService()
    raw = _docx_with_table()
    segments = extractor.extract_segments(raw, "report.docx")
    assert all(s.source_location.page is None for s in segments)
    assert "فصل اول" in segments[0].text
    assert any(s.source_location.paragraph == 2 and "رضایی" in s.text for s in segments)
    assert any(s.source_location.table == 1 and s.source_location.row == 2
               and "احمدی" in s.text for s in segments)
    assert any(s.source_location.paragraph == 3 and "۱۴ آبان" in s.text for s in segments)
    assert [s.document_order for s in segments] == list(range(len(segments)))
    assert any(s.source_location.section == "فصل اول" for s in segments[1:])
    assert "گزارش هزینه‌ها" in extractor.extract(raw, "report.docx")


def test_stage11_bounded_overlap_and_no_document_loss():
    extractor = DocumentExtractionService()
    source = "متن " + "نمونه " * 600 + "بخش انتهایی"
    segments = extractor.extract_segments(source.encode(), "long.txt")
    assert len(segments) >= 3
    assert all(0 < len(s.text) <= extractor.MAX_SEGMENT_CHARACTERS for s in segments)
    assert all(s.source_location.paragraph == 1 for s in segments)
    assert all(s.text in source for s in segments)
    for first, second in zip(segments, segments[1:]):
        assert first.text[-30:] in second.text
    assert "بخش انتهایی" in segments[-1].text


def test_stage11_retrieves_names_dates_numbers_and_paragraph_positions():
    extractor = DocumentExtractionService()
    service = DocumentRetrievalService(extractor)
    raw = (
        "تاریخ جلسه کمیته فناوری ۱۴ آبان ۱۴۰۵ است.\n\n"
        "آقای رضایی مسئول بررسی امنیت سامانه است.\n\n"
        "بودجه اولیه پروژه ۳۵۰ میلیون تومان تعیین شد."
    ).encode()
    for query, quote, paragraph in [
        ("تاریخ جلسه", "۱۴ آبان ۱۴۰۵", 1),
        ("مسئول بررسی امنیت", "آقای رضایی", 2),
        ("بودجه اولیه پروژه", "۳۵۰ میلیون", 3),
    ]:
        result = asyncio.run(service.retrieve_async(raw, "a.txt", query, top_k=1))
        assert result.status == "found"
        assert quote in result.evidence[0].segment.text
        assert result.evidence[0].segment.source_location.paragraph == paragraph


def test_stage11_normalizes_arabic_variants_zwnj_and_digits_only_for_search():
    service = DocumentRetrievalService(DocumentExtractionService())
    source = "صورت‌جلسه در ۱۴ آبان ۱۴۰۵ تهیه شد.\n\nشركت كاوش در پرونده ثبت شد."
    segments = service._extractor.extract_segments(source.encode(), "report.txt")
    a = service.retrieve_segments(segments, "صورت جلسه 14 آبان 1405", top_k=1)
    b = service.retrieve_segments(segments, "شرکت کاوش", top_k=1)
    assert a.status == b.status == "found"
    assert "۱۴ آبان ۱۴۰۵" in a.evidence[0].segment.text
    assert "شركت كاوش" in b.evidence[0].segment.text


def test_stage11_not_found_and_ambiguous_conflict_with_top_k_one():
    service = DocumentRetrievalService(DocumentExtractionService())
    raw = "تاریخ جلسه ۱۴ آبان ۱۴۰۵ است.\n\nتاریخ جلسه ۱۵ آبان ۱۴۰۵ است."
    segments = service._extractor.extract_segments(raw.encode(), "a.txt")
    ambiguity = service.retrieve_segments(segments, "تاریخ جلسه", top_k=1)
    assert ambiguity.status == "ambiguous"
    assert len(ambiguity.evidence) == 1
    missing = service.retrieve_segments(segments, "واکسن کودکان", top_k=3)
    assert missing.status == "not_found" and not missing.evidence


def test_stage11_distinguishes_adjacent_different_topics():
    service = DocumentRetrievalService(DocumentExtractionService())
    raw = "بودجه اولیه پروژه ۳۵۰ میلیون تومان است.\n\nجلسه در ۱۴ آبان ۱۴۰۵ برگزار شد."
    segments = service._extractor.extract_segments(raw.encode(), "a.txt")
    result = service.retrieve_segments(segments, "بودجه اولیه پروژه")
    assert result.status == "found"
    assert len(result.evidence) == 1


@pytest.mark.parametrize("query", ["", "\n\t", "و در به", "x" * 513, "آزمون\x00"])
def test_stage11_bad_query_fails_before_file_parsing(query):
    service = DocumentRetrievalService(DocumentExtractionService())
    with pytest.raises(RetrievalInputError):
        asyncio.run(service.retrieve_async(b"not a pdf", "a.pdf", query))


@pytest.mark.parametrize("top_k", [0, 9, 1.5, True])
def test_stage11_bad_topk_rejected(top_k):
    service = DocumentRetrievalService(DocumentExtractionService())
    with pytest.raises(RetrievalInputError):
        service.retrieve_segments([], "آزمایش", top_k=top_k)


def test_stage11_existing_extract_validation_and_no_text_unchanged():
    extractor = DocumentExtractionService()
    with pytest.raises(InvalidTextEncodingError):
        extractor.extract_segments(b"\xff", "a.txt")
    with pytest.raises(NoExtractableTextError):
        extractor.extract_segments(b" \n", "a.txt")
    with pytest.raises(DocumentLimitError):
        extractor.extract_segments(b"a" * (extractor.MAX_INPUT_BYTES + 1), "a.txt")


def test_stage11_di_resolves_retriever_without_model_inference():
    bootstrap_di()
    service = resolve(DocumentRetrievalService)
    assert isinstance(service, DocumentRetrievalService)
    result = asyncio.run(service.retrieve_async(
        "بودجه اولیه پروژه ۳۵۰ میلیون تومان است.".encode(), "a.txt", "بودجه اولیه"
    ))
    assert result.status == "found"


def test_stage11_frozen_stage9_dev_recall():
    result = evaluate()
    assert result["source_split"] == "dev"
    assert result["evaluated_queries"] == 15
    assert 0.80 <= result["recall_at_1"] <= result["recall_at_3"] <= 1.0
    assert all(row["recall_at_3"] for row in result["records"])


def test_stage11_ambiguous_people_with_same_responsibility():
    service = DocumentRetrievalService(DocumentExtractionService())
    raw = "مسئول پیگیری آقای رضایی است.\n\nمسئول پیگیری خانم احمدی است."
    segments = service._extractor.extract_segments(raw.encode(), "a.txt")
    result = service.retrieve_segments(segments, "مسئول پیگیری", top_k=1)
    assert result.status == "ambiguous"
    assert len(result.evidence) == 1
