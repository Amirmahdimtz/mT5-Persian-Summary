"""Stage 5 orchestration tests: no weights, network, or HTTP required."""
from __future__ import annotations

import asyncio
import time
from unittest.mock import Mock

import pytest

from src.core.services.summarization.document_extraction_service import (
    CorruptedDocumentError, DocumentLimitError, DocumentParsingError,
    EmptyDocumentError, NoExtractableTextError, PasswordProtectedPdfError,
    UnsupportedDocumentTypeError,
)
from src.core.services.summarization.long_text_summarization_service import (
    SummarizationInputError, SummarizationLimitError, SummarizationNoProgressError,
)
from src.core.services.summarization.summarization_service import (
    DocumentInput, FileSummaryResult, MultiFileSummaryResult,
    SummarizationRequestError, SummarizationService, TextSummaryResult,
)
from src.core.services.summarization.text_chunking_service import ChunkingLimitError
from src.infrastructure.ml.mt5_model_provider import (
    ModelInferenceError, ModelLoadError, ModelOutputError,
)


class FakeLongTextService:
    def __init__(self, *, summary="خلاصه فارسی", failures=None, delay=0):
        self.summary = summary
        self.failures = failures or {}
        self.delay = delay
        self.calls = []
        self.active = 0
        self.peak = 0

    async def summarize_async(self, text, summary_length="medium"):
        self.calls.append((text, summary_length))
        self.active += 1
        self.peak = max(self.peak, self.active)
        try:
            if self.delay:
                await asyncio.sleep(self.delay)
            if text in self.failures:
                raise self.failures[text]
            return self.summary if not callable(self.summary) else self.summary(text)
        finally:
            self.active -= 1


class FakeExtractor:
    def __init__(self, *, extracts=None, errors=None, delay=0):
        self.extracts = extracts or {}
        self.errors = errors or {}
        self.delay = delay
        self.calls = []

    def extract(self, content, filename):
        self.calls.append((content, filename))
        if self.delay:
            time.sleep(self.delay)
        if filename in self.errors:
            raise self.errors[filename]
        if not isinstance(filename, str) or not filename.lower().endswith((".txt", ".pdf", ".docx")):
            raise UnsupportedDocumentTypeError("unsupported")
        if not isinstance(content, bytes):
            raise CorruptedDocumentError("bad bytes")
        if not content:
            raise EmptyDocumentError("empty")
        return self.extracts.get(filename, "متن سند")


def service(extractor=None, long_text=None):
    extractor = extractor or FakeExtractor()
    long_text = long_text or FakeLongTextService()
    return SummarizationService(extractor, long_text), extractor, long_text


def run(coroutine):
    return asyncio.run(coroutine)


@pytest.mark.parametrize("length", ["short", "medium", "long"])
def test_text_valid_and_length_passthrough(length):
    svc, extractor, fake = service()
    text = "  متن فارسی برای خلاصه‌سازی  "
    result = run(svc.summarize_text_async(text, length))
    assert result == TextSummaryResult("خلاصه فارسی", length, len(text), len("خلاصه فارسی"))
    assert fake.calls == [(text, length)]
    assert extractor.calls == []


def test_text_default_and_long_delegation_exactly_once():
    fake = FakeLongTextService(summary=lambda text: "خلاصه بلند")
    svc, _, _ = service(long_text=fake)
    text = "متن طولانی " * 1000
    result = run(svc.summarize_text_async(text))
    assert result.summary == "خلاصه بلند"
    assert result.input_characters == len(text)
    assert fake.calls == [(text, "medium")]


@pytest.mark.parametrize("text", ["", "   ", "\n\t", None, 4, b"bytes", ["متن"]])
def test_reject_invalid_text_without_model_call(text):
    svc, _, fake = service()
    with pytest.raises(SummarizationInputError):
        run(svc.summarize_text_async(text))
    assert not fake.calls


@pytest.mark.parametrize("length", ["LONG", "tiny", "", None, 2, ["short"]])
def test_invalid_length_prevents_processing(length):
    svc, extractor, fake = service()
    with pytest.raises(SummarizationInputError):
        run(svc.summarize_text_async("متن", length))
    with pytest.raises(SummarizationInputError):
        run(svc.summarize_file_async(b"abc", "a.txt", length))
    with pytest.raises(SummarizationInputError):
        run(svc.summarize_files_async([DocumentInput("a.txt", b"a")], length))
    assert not extractor.calls and not fake.calls


@pytest.mark.parametrize("output", ["", " \n ", None, 123])
def test_empty_or_invalid_model_output_rejected(output):
    svc, _, _ = service(long_text=FakeLongTextService(summary=output))
    with pytest.raises(ModelInferenceError, match="no usable text"):
        run(svc.summarize_text_async("متن"))


@pytest.mark.parametrize("error", [
    ModelLoadError("private model path"), ModelOutputError("no output"),
    ModelInferenceError("inference"), ChunkingLimitError("max chars"),
    SummarizationLimitError("calls"), SummarizationNoProgressError("no progress"),
])
def test_downstream_errors_propagate_for_text_and_single_file(error):
    fake = FakeLongTextService(failures={"متن سند": error})
    svc, _, _ = service(long_text=fake)
    with pytest.raises(type(error)):
        run(svc.summarize_text_async("متن سند"))
    with pytest.raises(type(error)):
        run(svc.summarize_file_async(b"data", "file.txt"))


@pytest.mark.parametrize("filename", ["a.txt", "b.PDF", "c.DoCx"])
def test_single_file_delegates_exact_extracted_text_and_metadata(filename):
    source = "متن استخراج‌شده\nخط دوم"
    svc, extractor, fake = service(extractor=FakeExtractor(extracts={filename: source}))
    result = run(svc.summarize_file_async(b"file bytes", filename, "long"))
    assert result == FileSummaryResult(
        filename, "long", True, "خلاصه فارسی", len(source), len("خلاصه فارسی")
    )
    assert extractor.calls == [(b"file bytes", filename)]
    assert fake.calls == [(source, "long")]


@pytest.mark.parametrize("error", [
    EmptyDocumentError("empty"), CorruptedDocumentError("invalid"),
    NoExtractableTextError("image-only"), PasswordProtectedPdfError("locked"),
    DocumentLimitError("too large"), DocumentParsingError("parser"),
])
def test_single_file_preserves_typed_extractor_error(error):
    svc, _, fake = service(extractor=FakeExtractor(errors={"a.pdf": error}))
    with pytest.raises(type(error)):
        run(svc.summarize_file_async(b"data", "a.pdf"))
    assert not fake.calls


def test_single_file_empty_extraction_does_not_infer():
    svc, _, fake = service(extractor=FakeExtractor(extracts={"empty.txt": " "}))
    with pytest.raises(SummarizationInputError):
        run(svc.summarize_file_async(b"data", "empty.txt"))
    assert not fake.calls


@pytest.mark.parametrize("bad_bytes", [None, "not bytes", bytearray(b"abc"), b""])
def test_invalid_bytes_handled_by_extractor(bad_bytes):
    svc, _, fake = service()
    with pytest.raises((CorruptedDocumentError, EmptyDocumentError)):
        run(svc.summarize_file_async(bad_bytes, "a.txt"))
    assert not fake.calls


def test_multifile_mixed_formats_order_and_independent_results():
    files = [DocumentInput("a.txt", b"1"), DocumentInput("b.pdf", b"2"), DocumentInput("c.docx", b"3")]
    fake = FakeLongTextService(summary=lambda text: "Summary: " + text)
    extracts = FakeExtractor(extracts={"a.txt":"first", "b.pdf":"second", "c.docx":"third"})
    svc, extractor, _ = service(extractor=extracts, long_text=fake)
    result = run(svc.summarize_files_async(files, "short"))
    assert isinstance(result, MultiFileSummaryResult)
    assert result.succeeded == 3 and result.failed == 0
    assert [x.filename for x in result.results] == [f.filename for f in files]
    assert [x.summary for x in result.results] == ["Summary: first", "Summary: second", "Summary: third"]
    assert fake.calls == [("first", "short"), ("second", "short"), ("third", "short")]
    assert [c[1] for c in extractor.calls] == ["a.txt", "b.pdf", "c.docx"]


def test_partial_success_does_not_leak_exception_or_document():
    extracted = {"good.txt":"SAFE", "secret.pdf": "private document", "later.docx":"LATER"}
    fake = FakeLongTextService(failures={"private document": ModelLoadError("sensitive token")})
    svc, _, _ = service(extractor=FakeExtractor(extracts=extracted), long_text=fake)
    result = run(svc.summarize_files_async([
        DocumentInput("good.txt", b"1"), DocumentInput("secret.pdf", b"2"), DocumentInput("later.docx", b"3")
    ]))
    assert result.succeeded == 2 and result.failed == 1
    assert [x.success for x in result.results] == [True, False, True]
    assert result.results[1].error_code == "ModelLoadError"
    assert "sensitive" not in str(result) and "private document" not in str(result)
    assert result.results[1].summary is None and result.results[1].input_characters is None


def test_all_failed_and_duplicate_names_are_not_merged():
    svc, _, fake = service(extractor=FakeExtractor(errors={"same.txt": CorruptedDocumentError("bad")}))
    result = run(svc.summarize_files_async([DocumentInput("same.txt", b"a"), DocumentInput("same.txt", b"b")]))
    assert len(result.results) == 2 and result.failed == 2
    assert [r.filename for r in result.results] == ["same.txt", "same.txt"]
    assert all(x.error_code == "CorruptedDocumentError" for x in result.results)
    assert not fake.calls


def test_invalid_member_content_becomes_item_failure():
    svc, _, _ = service()
    result = run(svc.summarize_files_async([DocumentInput("a.txt", b"a"), DocumentInput("b.txt", None)]))
    assert result.succeeded == 1 and result.failed == 1
    assert result.results[1].error_code == "CorruptedDocumentError"


@pytest.mark.parametrize("files", [[], (), None, "abc", b"bytes", ["a.txt"], [{"filename":"a.txt"}], [None]])
def test_invalid_collection_is_a_request_error(files):
    svc, extractor, fake = service()
    with pytest.raises(SummarizationRequestError):
        run(svc.summarize_files_async(files))
    assert not extractor.calls and not fake.calls


def test_file_count_is_bounded_before_processing():
    svc, extractor, fake = service()
    files = [DocumentInput(f"{i}.txt", b"ok") for i in range(svc.MAX_FILES + 1)]
    with pytest.raises(SummarizationRequestError):
        run(svc.summarize_files_async(files))
    assert not extractor.calls and not fake.calls


def test_no_unbounded_inference_concurrency_and_all_results():
    fake = FakeLongTextService(delay=0.001)
    svc, _, _ = service(long_text=fake)
    files = [DocumentInput(f"{i}.txt", b"x") for i in range(svc.MAX_FILES)]
    result = run(svc.summarize_files_async(files))
    assert len(result.results) == svc.MAX_FILES
    assert fake.peak == 1


def test_cancellation_escapes_and_stops_later_files():
    entered = asyncio.Event()
    class CancellingLongText(FakeLongTextService):
        async def summarize_async(self, text, summary_length="medium"):
            self.calls.append((text, summary_length))
            entered.set()
            await asyncio.Future()

    fake = CancellingLongText()
    svc, extractor, _ = service(long_text=fake)
    async def execute():
        task = asyncio.create_task(svc.summarize_files_async([
            DocumentInput("first.txt", b"1"), DocumentInput("later.txt", b"2")
        ]))
        await entered.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    run(execute())
    assert [x[1] for x in extractor.calls] == ["first.txt"]


def test_unexpected_bug_not_silently_converted_to_file_failure():
    svc, _, _ = service(long_text=FakeLongTextService(failures={"متن سند": KeyError("bug")}))
    with pytest.raises(KeyError, match="bug"):
        run(svc.summarize_files_async([DocumentInput("a.txt", b"1")]))


def test_extraction_runs_off_event_loop_thread():
    svc, _, _ = service(extractor=FakeExtractor(delay=0.09))
    async def execute():
        operation = asyncio.create_task(svc.summarize_file_async(b"abc", "doc.txt"))
        await asyncio.sleep(0.02)
        was_responsive = not operation.done()
        result = await operation
        return was_responsive, result
    responsive, result = run(execute())
    assert responsive and result.success


def test_injected_constructor_accepts_explicit_fakes():
    svc, extractor, fake = service()
    assert svc._extractor is extractor
    assert svc._long_text_service is fake
    assert SummarizationService.__dict__["__di_inject__"] is True


def test_input_list_mutation_during_await_does_not_change_result_order():
    files = [DocumentInput("original.txt", b"a")]
    svc, _, _ = service(long_text=FakeLongTextService(delay=0.02))
    async def execute():
        task = asyncio.create_task(svc.summarize_files_async(files))
        await asyncio.sleep(0.005)
        files.append(DocumentInput("injected.txt", b"b"))
        return await task
    result = run(execute())
    assert [x.filename for x in result.results] == ["original.txt"]
