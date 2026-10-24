"""Stage 6 HTTP contracts and ingress security, no real mT5 weights."""

from __future__ import annotations

import asyncio
from concurrent.futures import CancelledError as FutureCancelledError
from io import BytesIO

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.datastructures import UploadFile

from src.application.summarization import summarization_controller as controller
from src.application.summarization.summarization_controller import SummarizationController
from src.application.summarization.upload_limit_middleware import UploadBodyLimitMiddleware
from src.core.services.summarization.document_extraction_service import (
    CorruptedDocumentError, InvalidTextEncodingError, NoExtractableTextError,
    PasswordProtectedPdfError, DocumentLimitError,
)
from src.core.services.summarization.long_text_summarization_service import (
    SummarizationLimitError,
)
from src.core.services.summarization.summarization_service import (
    DocumentInput, FileSummaryResult, MultiFileSummaryResult,
    SummarizationService, TextSummaryResult,
)
from src.infrastructure.di.bootstrap import bootstrap_di
from src.infrastructure.di.inject import resolve
from src.infrastructure.ml.mt5_model_provider import ModelInferenceError, ModelLoadError
from src.infrastructure.utils.config_reader import ConfigReader
from src.host.app import app, create_app


@pytest.fixture
def fake(monkeypatch):
    state = {"text": [], "file": [], "files": [], "error": None, "single": None, "multi": None}

    async def text_async(self, text, summary_length="medium"):
        state["text"].append((text, summary_length))
        if state["error"]: raise state["error"]
        return TextSummaryResult("خلاصه", summary_length, len(text), len("خلاصه"))

    async def file_async(self, content, filename, summary_length="medium"):
        state["file"].append((content, filename, summary_length))
        if state["error"]: raise state["error"]
        return state["single"] or FileSummaryResult(filename, summary_length, True, "خلاصه", 9, 5)

    async def files_async(self, files, summary_length="medium"):
        state["files"].append((files, summary_length))
        if state["error"]: raise state["error"]
        if state["multi"]: return state["multi"]
        return MultiFileSummaryResult(tuple(
            FileSummaryResult(f.filename, summary_length, True, "خلاصه", 9, 5) for f in files
        ))

    monkeypatch.setattr(SummarizationService, "summarize_text_async", text_async)
    monkeypatch.setattr(SummarizationService, "summarize_file_async", file_async)
    monkeypatch.setattr(SummarizationService, "summarize_files_async", files_async)
    return state


@pytest.fixture
def client(fake):
    with TestClient(app) as http:
        yield http


def document(name="a.txt", data=b"hello", mime="text/plain"):
    return (name, data, mime)


@pytest.mark.parametrize("length", ["short", "medium", "long"])
def test_text_valid_delegates_exactly_once(client, fake, length):
    text = "سلام فارسی"
    response = client.post("/api/v1/summarization/text", json={"text": text, "summary_length": length})
    assert response.status_code == 200, response.text
    assert response.json() == {"summary": "خلاصه", "summary_length": length,
                               "input_characters": len(text), "output_characters": len("خلاصه")}
    assert fake["text"] == [(text, length)]


def test_text_default_length(client, fake):
    assert client.post("/api/v1/summarization/text", json={"text": "فارسی"}).status_code == 200
    assert fake["text"] == [("فارسی", "medium")]


@pytest.mark.parametrize("body", [
    {}, {"text": ""}, {"text": " \n\t "}, {"text": None}, {"text": 12},
    {"text": "abc", "summary_length": "tiny"}, {"text": "x" * 200001},
    {"text": "x", "extra": "secret"},
])
def test_text_validation_never_infers(client, fake, body):
    response = client.post("/api/v1/summarization/text", json=body)
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "RequestValidationError"
    assert not fake["text"]
    assert "secret" not in response.text


def test_invalid_json_does_not_echo_input(client, fake):
    r = client.post("/api/v1/summarization/text", data='{ "text": "PRIVATE",',
                    headers={"content-type": "application/json"})
    assert r.status_code == 422 and "PRIVATE" not in r.text
    assert not fake["text"]


@pytest.mark.parametrize("exception,status", [
    (ModelLoadError("secret token"),503),
    (ModelInferenceError("private document"),500),
    (SummarizationLimitError("trace"),413),
])
def test_text_typed_errors_redacted(client, fake, exception, status):
    fake["error"] = exception
    r = client.post("/api/v1/summarization/text", json={"text": "فارسی"})
    assert r.status_code == status
    assert "secret" not in r.text and "private" not in r.text and "trace" not in r.text


def test_text_empty_model_result_is_failure(client, fake, monkeypatch):
    async def empty(self, text, summary_length):
        return TextSummaryResult("", summary_length, 1, 0)
    monkeypatch.setattr(SummarizationService, "summarize_text_async", empty)
    r = client.post("/api/v1/summarization/text", json={"text": "سلام"})
    assert r.status_code == 500


@pytest.mark.parametrize("entry", [
    document(), document("b.PDF", b"%PDF fake", "application/pdf"),
    document("c.docx", b"fakezip", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
])
def test_file_formats_and_filename_preserved(client, fake, entry):
    r = client.post("/api/v1/summarization/file", files={"file": entry}, data={"summary_length": "long"})
    assert r.status_code == 200, r.text
    assert r.json()["filename"] == entry[0]
    assert r.json()["summary_length"] == "long"
    assert fake["file"] == [(entry[1], entry[0], "long")]


@pytest.mark.parametrize("entry,status", [
    (document("zero.txt", b""),400),
    (document("a.exe", b"abc"),415),
    (document("../secret.txt", b"abc"),400),
    (document("a/b.txt", b"abc"),400),
    (document("a.pdf", b"fake", "text/plain"),415),
])
def test_invalid_upload_rejected_preinference(client, fake, entry, status):
    r = client.post("/api/v1/summarization/file", files={"file": entry})
    assert r.status_code == status, r.text
    assert not fake["file"]


def test_missing_file_and_bad_multipart(client, fake):
    r = client.post("/api/v1/summarization/file", data={"summary_length": "medium"})
    assert r.status_code == 415
    r = client.post("/api/v1/summarization/file", files={"other": document()})
    assert r.status_code == 422
    r = client.post("/api/v1/summarization/file", content=b"bad multipart",
                    headers={"content-type": "multipart/form-data; boundary=X"})
    assert r.status_code == 400
    assert not fake["file"]


@pytest.mark.parametrize("exception,status", [
    (CorruptedDocumentError("private"),422),
    (InvalidTextEncodingError("private"),422),
    (PasswordProtectedPdfError("private"),422),
    (NoExtractableTextError("private"),422),
    (DocumentLimitError("private"),413),
    (ModelLoadError("private"),503),
    (ModelInferenceError("private"),500),
])
def test_single_typed_errors(client, fake, exception, status):
    fake["error"] = exception
    r = client.post("/api/v1/summarization/file", files={"file": document()})
    assert r.status_code == status and "private" not in r.text


def test_file_too_large_preinference(client, fake, monkeypatch):
    monkeypatch.setattr(controller, "_MAX_FILE_BYTES", 2)
    r = client.post("/api/v1/summarization/file", files={"file": document(data=b"abc")})
    assert r.status_code == 413 and not fake["file"]


def test_bounded_reader_does_not_read_entire_unknown_size(monkeypatch):
    class UnknownSize:
        filename = "a.txt"
        size = None
        def __init__(self): self.read_sizes=[]; self.buffer=BytesIO(b"a"*9)
        async def read(self, n): self.read_sizes.append(n); return self.buffer.read(n)
    upload=UnknownSize()
    with pytest.raises(Exception) as caught:
        asyncio.run(controller._read_upload_async(upload, 8))
    assert caught.value.status_code == 413
    assert max(upload.read_sizes) <= controller._READ_CHUNK_BYTES
    assert all(n > 0 for n in upload.read_sizes)


def test_multifile_order_duplicate_filenames_and_counts(client, fake):
    entries = [document("same.txt", b"one"), document("same.txt", b"two"), document("z.pdf", b"x", "application/pdf")]
    r = client.post("/api/v1/summarization/files", files=[("files", entry) for entry in entries])
    assert r.status_code == 200, r.text
    assert [x.filename for x in fake["files"][0][0]] == [x[0] for x in entries]
    assert [x.content for x in fake["files"][0][0]] == [x[1] for x in entries]
    assert [x["filename"] for x in r.json()["results"]] == [x[0] for x in entries]
    assert (r.json()["succeeded"], r.json()["failed"]) == (3,0)


def test_multifile_partial_and_all_failure_preserved(client, fake):
    ok = FileSummaryResult("same.txt", "medium", True, "خلاصه", 4, 5)
    bad = FileSummaryResult("same.txt", "medium", False, error_code="ModelLoadError",error_message="token=secret!")
    fake["multi"] = MultiFileSummaryResult((ok,bad))
    files = [("files",document("same.txt", b"one")), ("files",document("same.txt", b"two"))]
    r = client.post("/api/v1/summarization/files", files=files)
    assert r.status_code == 200, r.text
    assert r.json()["succeeded"] == 1 and r.json()["failed"] == 1
    assert r.json()["results"][1]["error_code"] == "ModelLoadError"
    assert "secret" not in r.text
    fake["multi"] = MultiFileSummaryResult((bad,bad))
    r = client.post("/api/v1/summarization/files", files=files)
    assert r.status_code == 200
    assert r.json()["failed"] == 2 and r.json()["succeeded"] == 0


def test_multifile_invalid_member_rejects_collection(client, fake):
    r = client.post("/api/v1/summarization/files", files=[("files",document()), ("files",document("bad.exe"))])
    assert r.status_code == 415 and not fake["files"]
    r = client.post("/api/v1/summarization/files", files=[("files",document("empty.txt",b""))])
    assert r.status_code == 400 and not fake["files"]


def test_multifile_limit_and_budget_prevents_inference(client, fake, monkeypatch):
    too_many = [("files",document(f"{i}.txt")) for i in range(33)]
    r = client.post("/api/v1/summarization/files", files=too_many)
    assert r.status_code == 413 and not fake["files"]
    monkeypatch.setattr(controller, "_MAX_FILE_BYTES", 20*1024*1024)
    # Controller budget set at 4 bytes without changing the middleware's upstream 32 MiB.
    # The isolated bounded reader is covered independently; use a minimal
    # standalone app with a smaller controller aggregate budget for HTTP.
    configured = resolve(ConfigReader)
    summarizer = resolve(SummarizationService)
    special = SummarizationController(summarizer, configured)
    special._max_total_bytes = 4
    small_app = FastAPI()
    small_app.include_router(special.api(),prefix="/api/v1/summarization")
    with TestClient(small_app) as http:
        r = http.post("/api/v1/summarization/files", files=[("files",document("a.txt", b"abc")), ("files",document("b.txt", b"abc"))])
    assert r.status_code == 413 and not fake["files"]


def test_close_uploads_on_success_and_fail(client, fake, monkeypatch):
    original = UploadFile.close
    names = []
    async def tracked(self):
        names.append(self.filename)
        return await original(self)
    monkeypatch.setattr(UploadFile,"close",tracked)
    client.post("/api/v1/summarization/file",files={"file":document("a.txt")})
    client.post("/api/v1/summarization/file",files={"file":document("bad.exe")})
    client.post("/api/v1/summarization/files",files=[("files",document("b.txt")),("files",document("c.txt"))])
    assert {"a.txt","bad.exe","b.txt","c.txt"}.issubset(names)


def test_batch_cancellation_propagates_and_closes(monkeypatch, fake):
    async def cancelled(self, files, summary_length="medium"):
        raise asyncio.CancelledError()
    monkeypatch.setattr(SummarizationService, "summarize_files_async", cancelled)
    # ASGI exception must not be swallowed into per-file success.
    with pytest.raises((asyncio.CancelledError, FutureCancelledError)):
        client = TestClient(app)
        client.post("/api/v1/summarization/files", files=[("files",document())])


def test_openapi_discovery_di_health_no_model_load():
    bootstrap_di()
    assert isinstance(resolve(SummarizationController), SummarizationController)
    assert isinstance(resolve(SummarizationService), SummarizationService)
    schema = create_app().openapi()
    for endpoint in ("text", "file", "files"):
        path = f"/api/v1/summarization/{endpoint}"
        assert "post" in schema["paths"][path]
        assert "responses" in schema["paths"][path]["post"]
    assert "/api/v1/health" in schema["paths"]
    with TestClient(app) as http:
        assert http.get("/api/v1/health").json() == {"status":"ok"}
        assert http.get("/docs").status_code == 200


def test_multipart_asgi_budget_applied_without_content_length():
    from src.application.summarization.summarization_controller import SummarizationController
    # One MiB framing allowance, so a 1.1 MiB file exceeds budget=8 bytes.
    special_app = FastAPI()
    special_app.include_router(SummarizationController(resolve(SummarizationService),resolve(ConfigReader)).api(),prefix="/api/v1/summarization")
    special_app.add_middleware(UploadBodyLimitMiddleware,api_prefix="/api/v1",max_total_bytes=8)
    with TestClient(special_app) as http:
        r = http.post("/api/v1/summarization/file", files={"file":document(data=b"x"*(1024*1024+50))}, headers={"content-length":"1"})
    assert r.status_code == 413
