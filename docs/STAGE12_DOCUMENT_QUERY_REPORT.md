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

## Windows integration failure and focused fixture correction (2026-11-03)

A real Windows run after GitHub Stage 12 commit `7a7647ac870de7b5e94f81d55e416df749c3cc3a` reported **96 passed / 16 setup errors / 2 warnings** for the focused set and **444 passed / 16 setup errors / 2 warnings** for the full test suite. No assertion failures were recorded. All 16 setup errors were one duplicated problem: the HTTP test fixture handed `DocumentQueryController` an empty `TestConfig` that does not implement `ConfigReader.get("api.upload.max_total_bytes")`. The error occurs during constructor configuration, before request handling; it does **not** establish a production controller or retrieval failure.

**Fix:** In `tests/test_stage12_document_query.py`, replace the handwritten test-only controller mount/fake config with `TestClient(app)` using `src.host.app.app`, including real configuration, constructor DI, controller auto discovery and pre-multipart ASGI upload middleware. The OpenAPI test also asserts that the existing Summarization API remains registered. No production file, request budget, status mapping, source retrieval, or model behavior is changed. A green Windows rerun is still required.

The service was also started via `python -m src.host.app` and reported application startup complete but could not bind to **127.0.0.1:8000 (WinError 10048)**. Another program holds that port; do **not** kill an unidentified process. Instead, select an alternate port and use it consistently:

```powershell
# Inspect which process is listening on 8000 without modifying it:
Get-NetTCPConnection -State Listen -LocalPort 8000 -ErrorAction SilentlyContinue |
    Select-Object LocalAddress, LocalPort, OwningProcess

# Launch on a free port in a dedicated terminal:
$env:env_type = "development"
.\.venv\Scripts\python.exe -m uvicorn src.host.app:app --host 127.0.0.1 --port 8001

# In another terminal, use port 8001 for the same smoke request:
curl.exe -sS -X POST "http://127.0.0.1:8001/api/v1/document_query/file" -F "file=@local_stage12_demo.txt;type=text/plain" -F "query=تاریخ جلسه بعدی"
```

The earlier isolated 31-test preflight did **not** cover the real config/middleware integration and should not be misrepresented as passing the actual HTTP test setup. **Stage 12 remains In Progress; Production GO has not been granted.** Execute focused/full Windows pytest and the new-port smoke test after pulling this fix.

## Windows post-fixture verification and duplicate multipart correction (2026-11-03)

After the real-App test-fixture patch, the user's Windows run at code SHA `5b28aa30b131b32ae14e34e08d286dc64a91c674` confirmed `compileall` success; **111 passed, 1 failed (3 warnings)** in the focused selection, and **459 passed, 1 failed (3 warnings)** in the complete suite. The prior 16 fixture errors were resolved: 459 of 460 full-suite tests passed. The one remaining test was `tests/test_stage12_document_query.py::test_stage12_http_repeated_query_rejected`, which expected HTTP 422 but received HTTP 415.

**Cause:** The test used the httpx `data=[("query","بودجه"),("query","هزینه")]` payload alongside `files={...}`. In the user's httpx/FastAPI stack, this did not yield a conforming multipart Content-Type; the pre-multipart ASGI middleware correctly rejected the request with 415 before controller-level duplicate validation. The regression test was exercising a **different HTTP request** than intended. The request's production behavior is correct; keep the middleware's Content-Type protection.

**Change (test only):** Encode file and repeated query fields in the `files` sequence using `(None, value)` for non-file entries. This is genuine multipart/form-data, and controller validation must now respond with HTTP 422 plus `InvalidFormFields`. A local minimal FastAPI/TestClient reproduction with httpx 0.28.1 verified the exact form shape and 422/status code but was **not** full Repo pytest. No runtime, interface, dependency or upload-protection change.

**Separate confirmation:** A development Uvicorn server started normally at `http://127.0.0.1:8001`, resolving the earlier port 8000 conflict without disturbing the existing listener. HTTP smoke output itself has not yet been provided. The third deprecation warning in the last Windows run comes from the malformed httpx `data` request and may disappear once the test is corrected; the two pre-existing warnings remain nonblocking.

**Stage remains In Progress** until the Windows full suite is green and an actual multipart HTTP request to the new route returns grounded evidence. Stage 10 Production QA remains a separate deferred NO-GO; Stage 13 hardening is not started.
