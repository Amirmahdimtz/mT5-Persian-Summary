# Stage 12 — Document Query API & Source-Grounded Answering

Status: **In Progress — implementation committed, Windows integration tests pending.**
Scope: separate HTTP feature for one TXT, text PDF or DOCX; existing summarization endpoints unchanged.

## HTTP contract

Route: POST /api/v1/document_query/file (multipart/form-data, discoverable via Swagger). Exactly one file, one required nonblank query of at most 512 characters, optional mode (answer by default, focused_summary), and optional summary_length (short/medium/long, default medium, only valid for focused_summary). Reject unexpected or duplicate form fields with HTTP 422. An explicitly provided summary_length in answer mode is rejected.

Response DTO: status (found, not_found, ambiguous), mode, query, answer (string or null), and evidence list. Every evidence entry carries verbatim text, location_type (page, paragraph, table_row), document_type, page, paragraph, section, table, row, and zero-based document_order. PDF pages are real parser numbers (one-based); DOCX page is null, never fabricated. The response adapter verifies answer provenance.

Both modes are **strictly extractive**, not generative. Answer returns an original cited source passage without rewriting names, dates or amounts. Focused_summary concatenates original on-topic excerpts in document order, with a character budget: short <= 320, medium <= 680, long <= 1200. Complete excerpts are selected; raw truncation is not allowed. A query that cannot be supported returns status=not_found, answer=null and evidence=[]. Ambiguous competing source evidence returns status=ambiguous, answer=null, and source excerpts for inspection. HTTP 200 is used for these semantic statuses.

The Core DocumentQueryService constructor-injects Stage 11 DocumentRetrievalService. The query is validated before reading full upload bytes. Candidate evidence requires at least 75% coverage of meaningful query terms and explicit date/person/numeric evidence for such factual questions. This is a **conservative lexical heuristic, not proof of entailment**; correct but implicit answers can be rejected, and contextual ambiguity remains a risk. The service never loads or calls mT5, so its unavailability does not affect this endpoint; no unsupported model-503 path is claimed.

## Upload security and compatibility

Shared file metadata, MIME/extension, filename and bounded streaming validation live in src/application/upload_validation.py. The existing summarization controller uses the same implementation, preserving its old helper names and test seams including _MAX_FILE_BYTES and _READ_CHUNK_BYTES. Existing UploadBodyLimitMiddleware now covers the new document_query/file route, retaining body-size cap, admission semaphore, idle timeout and bounded temporary spool. Known errors are mapped to generic redacted messages: 400 invalid/empty upload, 413 oversized input, 415 unsupported media, 422 malformed query/document/form, 500 unexpected parser failure or invalid answer provenance, 503 upload-capacity exhaustion. The old summarization routes never require query.

## Changed files

- New src/core/services/document_query/document_query_service.py
- New src/application/document_query/document_query_controller.py
- New src/application/document_query/dtos/document_query_dto.py
- New src/application/upload_validation.py
- Updated src/application/summarization/summarization_controller.py
- Updated src/application/summarization/upload_limit_middleware.py
- New tests/test_stage12_document_query.py
- Updated docs/POST_MVP_DEVELOPMENT_PLAN.md and docs/IMPLEMENTATION_PROGRESS.md
- New docs/STAGE12_DOCUMENT_QUERY_REPORT.md

No new dependencies, model/config adjustments, Stage 10 quality gate changes, or Stage 11 retrieval algorithm changes.

## Verification

Assistant preflight in an isolated environment using source-equivalent Stage 11 extraction/retrieval and the new Stage 12 service, FastAPI controller, DTO and shared upload helper: **29 tests passed, one unrelated httpx deprecation warning**. These included literal dates/names/amounts, conflicting evidence, not-found handling, topic filtering, length limits, DOCX source locations, API/OpenAPI responses, invalid fields, duplicates, unsafe uploads, and redacted errors. The test harness used stub DI/ConfigReader and did not import the real repository-wide application or ASGI middleware. It had pypdf 5.9.0 (not the project's required 6.21.2), and no transformers/model weights. **Integrated repository pytest and real HTTP middleware tests were not run by the assistant.** Last verified user-run pre-Stage-12 full suite: 429 passed, 2 warnings.

Stage 12 stays **In Progress** until Windows integration/full regression suite and Swagger + multipart smoke tests pass. No independent semantic correctness, OCR support or Production GO is asserted.

## Local Windows PowerShell verification

Run from the repository root, with Python virtual environment already created:

    git pull --ff-only origin main
    $env:env_type = "development"
    .\.venv\Scripts\python.exe -m pip install -r requirements.txt
    .\.venv\Scripts\python.exe -m pip check
    .\.venv\Scripts\python.exe -m compileall -q src benchmarks tests
    .\.venv\Scripts\python.exe -m pytest -q tests/test_stage12_document_query.py tests/test_summarization_api.py tests/test_stage11_retrieval.py tests/test_stage7_hardening.py
    .\.venv\Scripts\python.exe -m pytest -q
    .\.venv\Scripts\python.exe -m src.host.app

In a separate PowerShell terminal, with the application running:

    Set-Content -LiteralPath ".\local_stage12_demo.txt" -Encoding utf8 -Value "جلسه بعدی در تاریخ ۱۴ آبان ۱۴۰۵ برگزار می‌شود."
    curl.exe -sS -X POST "http://127.0.0.1:8000/api/v1/document_query/file" -F "file=@local_stage12_demo.txt;type=text/plain" -F "query=تاریخ جلسه بعدی"
    curl.exe -sS -X POST "http://127.0.0.1:8000/api/v1/document_query/file" -F "file=@local_stage12_demo.txt;type=text/plain" -F "query=تاریخ جلسه بعدی" -F "mode=focused_summary" -F "summary_length=short"

Check http://127.0.0.1:8000/docs for the new operation and unchanged Summarization routes. Both smoke responses should cite the original phrase and report true TXT paragraph=1. Do not commit local output files containing private documents.

Stage 13 should harden real Persian PDF/DOCX coverage, adversarial queries, semantic consistency, operational resource limits and independent human review. Stage 10's Production-quality NO-GO remains a separate, deferred constraint.
