# Stage 11 — Source-anchored Extraction & Retrieval

**Stage:** 11 of Post-MVP Development Plan (Evidence-aware Extraction & Retrieval)  
**Status:** Completed (Development engineering acceptance; Production/real-field semantic QA remains separate)  
**Scope:** Structured retrieval from one in-memory TXT, text-based PDF or DOCX; **not** a new HTTP/QA endpoint. Stage 12 owns API/answer generation.

## Core implementation and invariants

The existing `DocumentExtractionService.extract(content, filename) -> str` contract remains unchanged. The additive `extract_segments(content, filename) -> tuple[DocumentSegment, ...]` returns frozen records with `text`, `source_location` and zero-based `document_order`. Evidence snippets originate from the parser's own text; no date, name, page number or paragraph is invented.

- **TXT:** 1-based paragraph number, separated by blank lines; sentence slices share the original paragraph location. Original Unicode is left in evidence (including ZWNJ and Persian digits).
- **PDF:** the original layout-mode pypdf extraction and conservative RTL repair are preserved. Its page index is **1-based from the actual PDF**, even when intervening pages have no text. Large-page excerpts retain that page number; PDF paragraph numbering is not guessed.
- **DOCX:** 1-based actual top-level paragraph index; headings with Word's `Heading` styles can provide a section label; table rows use 1-based `table`/`row`. **DOCX page is always null** (Word pagination depends on rendering). Merged table cells are emitted only once.
- **Boundaries and memory:** bounded sentence excerpts; source-only overlapping windows for long spans (1200 characters, 120-character overlap), at most 8192 excerpts. Existing 20 MiB input, 500 PDF page, DOCX ZIP member/uncompressed budgets and 5,000,000-character parsing cap remain; TXT structured extraction also enforces the 5,000,000-character cap. Excess work fails with `DocumentLimitError` rather than truncating silently.
- **Safety:** no disk temp files, no network/Embedding downloads, no mT5 load, no storage, no logs containing private text; standard extraction errors continue to be raised. A resource-intensive parse/rank request goes through `asyncio.to_thread` so it does not block the ASGI event loop. Stage 12 must apply the pre-existing HTTP upload and request admission budgets before invoking this method.

`DocumentRetrievalService` is registered via `@inject`, receiving `DocumentExtractionService` by concrete constructor type; auto discovery loads it. `retrieve_async(content, filename, query, *, top_k=3)` uses the additive extraction route. `retrieve_segments(segments, query, *, top_k=3)` can be tested directly without a file/model.

The search-only normalization folds Arabic/Persian Kaf/Ya, Arabic/Persian/ASCII digits, zero-width joiners, common diacritics, whitespace and case. **The evidence returned is never normalized or rewritten.** A bounded lexical match requires at least 60% of the meaningful query terms, then ranks full coverage and exact phrase matches. Ties are deterministic by document order. Max query length is 512 characters, `1 <= top_k <= 8`, and collection size/memory are bounded. There is no embedding, LLM inference, answer generation, fact interpolation or unsupported field extrapolation.

Retrieval returns a frozen `RetrievalResult(status, evidence)`, with `status` in `found | not_found | ambiguous`. Empty/irrelevant queries fail validation or return `not_found`; multiple similarly relevant passages containing differing **explicit digits or named persons** produce `ambiguous`, including with `top_k=1`. **Ambiguous means unresolved potentially conflicting evidence, not adjudicated logical contradiction.** No answer is fabricated. Exact knowledge/entailment of negation, subject coreference, dates and compound names is not claimed. Ranking is a conservative Stage 11 lexical baseline; hybrid or embedding retrieval should only follow measured quality need and a resource/license decision.

## Reproducible Development retrieval benchmark

`benchmarks/fixtures/stage11_retrieval_dev_v1.json` adds **15 manually labeled retrieval questions** (date, person, number, action and topic) against *the already tracked Stage 9 synthetic Development* texts in `benchmarks/fixtures/quality_v1.json`. The original Stage 9 fixtures and all holdout labels remain unchanged. Only Development cases are indexed and queried; holdout is not evaluated or scored. Labels contain exact source excerpts, validated against the original Development source.

The no-overwrite runner writes case-level source locations, binary quote-hit `Recall@1`, `Recall@3`, source dataset SHA and label SHA. It **does not** claim answer-generation correctness, a hallucination rate or independent human adjudication.

Run in the user Windows checkout after pulling the Stage 11 commit:

```powershell
$env:env_type = 'development'
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m compileall -q src benchmarks tests
.\.venv\Scripts\python.exe -m pytest -q tests/test_stage11_retrieval.py tests/test_document_extraction_service.py tests/test_di.py
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m benchmarks.stage11_retrieval_benchmark --output ".\local_stage11_retrieval_dev_v1.json"
Get-Content -LiteralPath ".\local_stage11_retrieval_dev_v1.json" -Raw
```

**Preflight run (assistant's isolated Python test harness, not the Repository):** 21 Stage 11 cases passed (0 failed), and 15/15 labeled Development queries hit their expected quote at top 1 and top 3 (`Recall@1=1.000`, `Recall@3=1.000`) using equivalent segment/retriever logic and a Development-only copy of the fixture. The harness used pypdf 5.9.0, python-docx 1.2.0, simplified DI and **did not** import the Repository's complete model/dependency stack; the Repository requires pypdf >=6.21.2 and `transformers` is not installed in the assistant runtime. These are explicitly **not** integrated project test results. No full-suite, API upload, actual PDF corpus or final recall score is certified until the user's Windows run. Existing latest user-confirmed Stage 10 full suite: 408 passed, 2 nonblocking warnings, prior to Stage 11 changes.

## Acceptance and remaining risk

- Stage 11 evidence extraction and ranking are additive; production/default summarization paths are unchanged.
- Unit cases target TXT paragraph boundaries, PDF pages across blank pages, DOCX headings/tables, exact evidence, overlap/limits, Persian normalization, responsible person, date/amount/topic retrieval, numeric/name ambiguity, not-found behavior, input limits and auto DI resolution.
- A measurable Stage 9 Development `Recall@K` report is available once run on the actual Windows environment.
- Limitations: lexical coverage may miss paraphrases/morphology, sentence splitting can lose qualifiers across boundaries, token-bounded admission and page-by-page source extraction should be stress tested on varied real Persian PDFs/DOCX, evidence can be ambiguous without literal contradiction, long-document indexing may be resource intensive. No answer quality or Stage 10 semantic-quality production approval is implied.

**Decision (2026-11-03):** Stage 11 is **Completed for Development engineering acceptance** after the user's verified Windows full-suite tests and 15-question labeled Development retrieval benchmark. Stage 12 may now implement the separate Document Query API. User-accepted Stage 10 quality limitations remain documented and are deferred, not falsely marked as passing the former Production GO quality gate.

## Stage 11 Windows integration verification and completion (2026-11-03)

The user provided the full Windows PowerShell terminal record of pulling GitHub `main` through `f103d19a92e89a07f84875b41148fa5bffe394e9`, installing the real requirements, and running the actual checked-out project tests plus the Stage 11 labeled Development benchmark.

- **Dependency and syntax validation:** `pip install -r requirements.txt` reported requirements satisfied, including `pypdf==6.21.2`, `python-docx==1.2.0`, `transformers==4.57.6`; `pip check` returned "No broken requirements found"; `compileall -q src benchmarks tests` completed without error.
- **Focused integration tests:** `pytest -q tests/test_stage11_retrieval.py tests/test_document_extraction_service.py tests/test_di.py` **85 passed, 0 failed in 8.27s**. This includes TXT/PDF/DOCX source-location regression cases, real DI discovery, existing extraction compatibility, invalid input, lexical normalization, `not_found`, and numeric/person `ambiguous` cases.
- **Full regression suite:** `pytest -q` **429 passed, 0 failed, 2 warnings in 31.44s**. The warnings were the already known Starlette TestClient/httpx deprecation and an httpx raw-content-upload deprecation. No failure or dependency mismatch was reported.
- **Actual Development benchmark:** `python -m benchmarks.stage11_retrieval_benchmark --output .\\local_stage11_retrieval_dev_v1.json` successfully wrote a **new local, untracked** report. The complete terminal-rendered JSON was independently parsed and checked for 15 distinct IDs, 15/15 `recall_at_1=true`, 15/15 `recall_at_3=true`, and 15 `status=found` records. The report includes source paragraph and document-order locations. **Recall@1=1.000 and Recall@3=1.000 on the fifteen existing, labeled Stage 9 synthetic Development queries only.** Source dataset SHA-256 recorded: `cc907d6b16a4b68685b280002bb0a0f550ce6ce3966941c8732702c016f8a9a9`. Labels SHA-256 recorded: `7fa910edc47c98f712d0f9f83eb646998f7eb859c4a4d2e42153ad524c6e770e`.
- **Scope of evidence:** The results confirm exact quote-level source retrieval and source-location plumbing, not answering quality, entailment, deep semantic retrieval, PDF scan/OCR, statistically valid production recall, or independent human validation on diverse real Persian documents. The 15-query metric does not exercise `not_found` or `ambiguous` cases; those statuses are covered by unit tests. This stage did not introduce a Document Query HTTP endpoint or load the mT5 model during retrieval.
- **Stage decision:** **Completed (Development engineering scope)**. No application code, model/config defaults, APIs, test gates or holdout datasets are changed by this signoff. The user-accepted Stage 10 quality shortfall is still explicitly deferred (not a Production GO). **Stage 12 is ready** to implement a separate optional Document Query API with grounded answer/focused-summary behavior, subject to its own tests and quality gates.
