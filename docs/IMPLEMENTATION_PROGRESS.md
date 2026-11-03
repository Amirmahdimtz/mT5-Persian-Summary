# Implementation Progress — mT5 Persian Summarization Service

## Stage Overview

| Stage | Status |
| --- | --- |
| 1. Project Setup, DI & FastAPI | Completed |
| 2. mT5 Model Integration | Completed |
| 3. Document Extraction | Completed |
| 4. Chunking & Long Text Summarization | Completed |
| 5. Main SummarizationService | Completed |
| 6. REST API & Upload Validation | Completed |
| 7. Testing, Security & Optimization | Completed |
| 8. Docker & Final Delivery | Completed |
| 9. Quality Benchmark & Root Cause | Completed |
| 10. General Summarization Quality | In Progress |
| 11. Evidence-aware Extraction & Retrieval | Not Started |
| 12. Document Query API | Not Started |
| 13. Quality Hardening & Delivery | Not Started |

- Last completed stage: **9** (engineering baseline only; not model quality approval)
- Active stage: **10 (initial reversible quality candidate and paired evaluation; human-reviewed inference pending)**
- Repository: `Amirmahdimtz/mT5-Persian-Summary`
- Branch: `main`
- Baseline: repository was empty (no initial commit or branch head).
- Stage 1 implementation commit: `d38c353e0d9776ed5f2b9ebecd75017ea7fb5f82` (`feat: initialize FastAPI architecture and dependency injection`).
- To check the latest branch head, run `git rev-parse HEAD`.

## Stage 1 — Changed Files

- `src/core/services/.gitkeep`: preserve the empty core services namespace in Git checkout.
- `src/host/app.py`: ASGI startup, DI bootstrap, configuration-driven local server.
- `src/host/res/appsettings.yaml`, `appsettings.development.yaml`: safe base/development settings.
- `src/application/web.py`: FastAPI initialization and controller discovery.
- `src/application/health/health_controller.py`: model-independent health endpoint.
- `src/infrastructure/di/inject.py`: constructor injection, typed registration, singleton resolution, circular dependency diagnostics.
- `src/infrastructure/di/reflection.py`: provider discovery in infrastructure → core → application order.
- `src/infrastructure/di/bootstrap.py`: idempotent DI bootstrap.
- `src/infrastructure/utils/config_reader.py`: YAML loader with dotted keys and per-process singleton semantics.
- `tests/test_app.py`, `tests/test_di.py`, `tests/test_configuration.py`, `tests/test_structure.py`: HTTP, DI, configuration and checkout-structure regression coverage.
- `requirements.txt`, `.python-version`, `.gitignore`, `README.md`: development dependencies, Python baseline and setup instructions.
- `Service_Architecture_Guide_FA.md`, `IMPLEMENTATION_PLAN.md`: unchanged project source references provided at Stage 1.
- `docs/IMPLEMENTATION_PROGRESS.md`: stage tracking.

## Technical Decisions

- Python 3.11+; FastAPI, Pydantic v2, Uvicorn, PyYAML, Pytest and HTTPX.
- Namespace-compatible `src.*` imports. `@inject` marks providers; reflection discovers providers instead of manual service registration.
- `ConfigReader` is the only Stage 1 singleton. Controllers and services are transient.
- Missing providers, invalid type hints, import errors and invalid controller contracts fail with actionable exceptions.
- `env_type=development` selects development YAML; other values select base YAML. No credentials are required.
- Health check is `GET /api/v1/health` with HTTP `200` and `{"status":"ok"}` using default configuration.
- No model inference, persistence, document extraction, Docker or summarization routes are implemented.

## Tests & Verification

Executed locally with Python 3.13.5 and the installed dependencies:

```bash
python -m compileall -q src tests
python -m pytest -q
```

- Syntax/compile: Passed.
- Pytest: **16 passed**, 0 failed.
- Real HTTP smoke: started `python -m src.host.app`; `GET /api/v1/health`, `/docs`, `/openapi.json` all returned **200**.
- Model-related integration tests: Not Run; outside Stage 1.
- Independent Python 3.11 environment: Not Run (local interpreter was Python 3.13.5).

## Known Issues / Constraints

- Application components are discovered on startup; import or DI configuration errors intentionally fail startup.
- The service is a Stage 1 scaffold, not yet a summarization API.
- Python 3.11 compatibility has not been independently executed, although code targets Python 3.11+.

## Next Stage Readiness

- Stage 1 acceptance criteria: Met in the available local test environment.
- Ready for Stage 2: model identifier/revision/license verification, a process-scoped ML provider, real inference smoke test, and mocked unit tests.

## Stage 1 Follow-up — Windows Validation and Test Compatibility (2026-10-24)

- User environment: Windows PowerShell, Python 3.12.10, FastAPI 0.162.0, pytest 9.1.1.
- Initial Windows run: `python -m compileall -q src tests` succeeded; `python -m pytest -q` reported 15 passed and 1 failed.
- Root cause: the discovery test accessed `route.path` on every item in `app.routes`; FastAPI returned an `_IncludedRouter` object without that attribute. Health HTTP and OpenAPI tests succeeded, indicating functional route discovery.
- Correction: `tests/test_app.py` now checks the public `app.openapi()["paths"]` contract instead of router internals. No application code or dependencies changed.
- Local regression validation: `python -m compileall -q src tests` passed; `python -m pytest -q` returned **16 passed, 0 failed** under Python 3.13.5, FastAPI 0.128.2.
- Windows post-fix rerun on Python 3.12.10/FastAPI 0.162.0: **Passed**. User verified `git pull --ff-only origin main` (fast-forward to `c625028a251677f49499a741d8080bed66bab363`), `python -m compileall -q src tests` (no errors), and `python -m pytest -q` (**16 passed, 0 failed, 1 non-blocking StarletteDeprecationWarning in 10.41s**).
- Windows HTTP smoke: `python -m uvicorn src.host.app:app --host 127.0.0.1 --port 8001` reached `Application startup complete` and served `GET /api/v1/health` with **HTTP 200 OK**. Swagger browser check on Windows was not reported.
- Windows service start: `python -m src.host.app` failed to bind port 8000 (WinError 10048, address already in use). This is an external port collision, not an application import/DI failure. Alternative: `python -m uvicorn src.host.app:app --host 127.0.0.1 --port 8001`.
- The third-party `starlette.testclient` deprecation warning is non-fatal; no dependency change was necessary for this correction.


## Stage 2 — mT5 Model Integration (2026-10-24)

- **Status: Completed**. Provider implementation and 36 automated tests are verified; the user independently completed a real CPU inference smoke test on Windows/Python 3.12.10 on 2026-10-24. The original sandbox could not run real inference; see Windows verification follow-up below.
- Starting main HEAD: 2466c4812f4a5b0ee4c91f439a46e34c4d389fc0 (verified via GitHub). Branch main had write permission and no active protection.
- Stage 2 changed files: src/infrastructure/ml/mt5_model_provider.py; src/infrastructure/ml/smoke_mt5_model.py; tests/test_mt5_model_provider.py; src/host/res/appsettings.yaml; src/host/res/appsettings.development.yaml; requirements.txt; README.md; docs/STAGE2_MODEL_VERIFICATION.md; docs/IMPLEMENTATION_PROGRESS.md.
- Architecture: existing DI/bootstrap/ConfigReader and health/controller code not changed. New @inject infrastructure provider is singleton per worker; constructor-injected ConfigReader; no model download/import at app startup. Model loaded on first valid summary under a lock. A second lock bounds concurrent inference. Async method uses asyncio.to_thread; synchronous method is CLI-only or to be called on worker threads. Model load errors are cached until restart.
- Model: nafisehNik/mt5-persian-summary at b575560ad967050e77a40f907abb1ebbeefb9a15; model-card MIT license; MT5ForConditionalGeneration / SentencePiece. Main-branch checkpoint is ~1.2 GB pytorch_model.bin, not safetensors; use trust_remote_code=False, weights_only=True. Alternative safetensors model considered; see docs/STAGE2_MODEL_VERIFICATION.md.
- Limits: 1000 input tokens including specials (from model-card example; not confirmed architectural maximum), 20,000 input chars (protective Stage-2 limit), decoder max_length=120. No silent truncation.
- Generation: num_beams=2, repetition_penalty=1.0, length_penalty=2.0, early_stopping=true, do_sample=false. No documented task prefix.
- CPU default, opt-in auto/cuda with validation; memory guidance >=8 GB available for first CPU test (estimate; not measured), use one worker until profiled.
- Dependencies added: transformers>=4.48,<5, torch>=2.6,<3, sentencepiece>=0.2,<0.3. Windows Python 3.12.10 dependency installation and CPU inference were subsequently verified on the user's machine.
- Verification: reconstructed local Python 3.13.5 workspace, python -m compileall -q src tests **Passed**; python -m pytest -q **36 passed, 0 failed** (20 new mocked model tests plus 16 retained Stage-1 regressions). Mock coverage includes DI resolve, singleton, config, validation, token guard, generation/decode, errors, one-time load, concurrency, async method and CPU selection.
- Real-model smoke command python -m src.infrastructure.ml.smoke_mt5_model: **Blocked (attempted, nonzero exit)** because transformers was not installed in sandbox, and external model download unavailable. No weight download, no Persian summary and no real RAM measurements. Windows real inference: **Passed in later user validation**; see follow-up below.
- Known issues: pickle checkpoint provenance risk; real model generation and Windows/Python 3.12 compatibility verified in user follow-up; model quality beyond Persian news unassessed; original non-blocking Starlette deprecation warning may remain.
- Next step: start Stage 3 document extraction in a separate request. The independent manual HTTP health request in the latest Windows log failed because no server startup was shown; run Uvicorn on port 8001 and recheck (the existing TestClient health regression already passed).
- Commit SHA: see repository main HEAD for this Stage-2 integration commit (the commit SHA cannot be stored in its own content without another commit).

## Stage 2 Follow-up — Windows CPU Real-Model Verification (2026-10-24)

- Evidence: user-provided PowerShell terminal transcript after fast-forward checkout of Stage 2 implementation commit `fd6b2a87c66f425133c649caddd594a49b9238a3`. Results below were executed by the user (not in the assistant's sandbox).
- Platform: Windows, PowerShell, Python **3.12.10**, CPU-only PyTorch **2.14.1+cpu**, Transformers **4.57.6**, SentencePiece **0.2.2**, FastAPI **0.162.0**, Pytest **9.1.1**.
- `python -m pip check`: **Passed** (`No broken requirements found.`).
- `ConfigReader().get("model")`: correct pinned model revision and CPU generation settings loaded.
- `bootstrap_di(); resolve(Mt5ModelProvider) is resolve(Mt5ModelProvider)`: **True** (provider resolved as a per-process singleton).
- `python -m compileall -q src tests`: **Passed**, no errors.
- `python -m pytest -q`: **36 passed, 0 failed, 1 non-blocking StarletteDeprecationWarning** in 10.72 seconds (16 Stage-1 regressions and 20 Stage-2 mocked provider cases).
- `python -m src.infrastructure.ml.smoke_mt5_model`: **Passed**; model tokenizer and approximately 1.20 GB `pytorch_model.bin` downloaded, model loaded successfully, generated non-empty Persian text:
  `اعلام کرد که در روزهای آینده در مناطق شمالی کشور بارش باران پیش بینی می شود.`
- Hugging Face cache folder was observed under the user's default Windows cache path. No RAM usage or summarization quality benchmark was measured.
- Non-blocking runtime warnings: symlink-disabled Windows cache (possible extra disk use), `hf_xet` unavailable (regular HTTP fallback), legacy T5 tokenizer behavior. A `model.safetensors` download progress bar was also seen at 13% *after* the summary output; origin/necessity of that additional transfer has not been established, and completion cannot be inferred.
- Manual `Invoke-RestMethod http://127.0.0.1:8001/api/v1/health` returned `Unable to connect to the remote server`. The supplied log does **not** show a preceding Uvicorn start command; check for a listening server on port 8001 before drawing conclusions about application HTTP functionality. The HTTP health route already passed the automated tests and previous Stage-1 Windows live test.
- **Acceptance:** Stage 2 criteria met: real short Persian inference returned a non-empty summary, DI resolved a singleton, configuration and token-generation behavior are covered by tests, failures are distinguishable. Stage 2 **Completed**, Stage 3 **Not Started**.
- Implementation commit: `fd6b2a87c66f425133c649caddd594a49b9238a3`. Follow-up documentation commit: see GitHub history after this record is published.

## Stage 3 — Document Extraction (2026-10-24)

- **Status: In Progress**; core extraction is implemented, but the declared
  pypdf >=6.21.2 dependency and full Stage 1/2 regression suite have not
  been executed in the target Windows/Python 3.12 environment.
- Starting HEAD: `67b63804cb62a83f4b88b0da0a26785287314ad5`;
  main write access and unprotected branch verified through GitHub.
- Changed files: `src/core/services/summarization/document_extraction_service.py`,
  `tests/test_document_extraction_service.py`, `requirements.txt`,
  `README.md`, and `docs/IMPLEMENTATION_PROGRESS.md`.
- Contract: `DocumentExtractionService.extract(content: bytes, filename: str) -> str`;
  convenience methods `extract_txt(content)`, `extract_pdf(content)`,
  `extract_docx(content)` return Unicode `str`. File extension selects
  format case-insensitively; corrupt content is not trusted. No FastAPI,
  storage, summarization, model loading, or database dependency.
- TXT policy: strict UTF-8 decoding with optional UTF-8 BOM; never guess
  encoding or ignore failures. Reject invalid binary control characters.
  Preserve Persian Unicode, numbers, punctuation and ZWNJ.
- PDF: pypdf (BSD-3-Clause, pure Python, Windows/Python 3.12 compatible),
  `PdfReader(BytesIO(...), strict=True)`; layout extraction with
  `layout_mode_strip_rotated=False` because plain extraction reversed Persian
  in local tests. Process pages in order, omit empty pages, reject encrypted
  PDFs, corrupted documents, excessive page count and no-extractable-text.
  Text layer is mandatory; OCR is not available. Alternative PyMuPDF uses
  AGPLv3 or a commercial license and adds compiled native components.
- DOCX: python-docx 1.2+ (MIT, Python >=3.9; lxml dependency), use
  `Document(BytesIO(...)).iter_inner_content()` to preserve document-order
  paragraphs and tables; traverse cell content and nested tables; do not
  duplicate merged cells. Unsupported .doc is rejected. Comments, headers,
  footers, text boxes, embedded objects and tracked-change text are not
  guaranteed. DOCX ZIP metadata is screened before XML parsing.
- Dependency changes: `pypdf>=6.21.2,<7.0`,
  `python-docx>=1.2,<2.0`. pypdf minimum chosen after reviewing published
  2025-2026 memory/CPU exhaustion security advisories; do not deploy the
  older version used by the isolated local test sandbox.
- Resource guards: input <=20 MiB, output <=5,000,000 chars, PDF <=500
  pages, DOCX <=2,000 ZIP entries, <=20 MiB per expanded member and
  <=80 MiB combined declared ZIP size. Stage 6/7 must enforce upload
  stream limits *before* the input is materialized in memory. These limits
  are conservative extraction-stage defenses, not an exhaustive sandbox.
- Normalization: CRLF/CR to LF, trim leading/trailing whitespace; do not
  collapse internal blank lines, transliterate, truncate or rewrite content.
- Exception policy: `UnsupportedDocumentTypeError`, `EmptyDocumentError`,
  `InvalidDocumentError`, `InvalidTextEncodingError`,
  `CorruptedDocumentError`, `PasswordProtectedPdfError`,
  `NoExtractableTextError`, `DocumentLimitError` and
  `DocumentParsingError`. Avoid raw document bytes or filenames in errors
  and logs; preserve causes via exception chaining.
- Unit/integration coverage: 50 parametrized test cases in
  `tests/test_document_extraction_service.py` covering TXT encoding,
  PDF Persian ToUnicode text layers, multipage and empty PDFs, encrypted
  and malformed PDFs, DOCX paragraphs/tables and bad ZIPs, limits, DI
  discovery, independence from FastAPI/model and no temporary files.
  PDF ToUnicode fixture is generated in memory using pypdf (synthetic
  font), and is NOT a real-world embedded-font Persian PDF quality test.
- Local isolated Python 3.13.5 sandbox (pypdf **5.9.0**, python-docx
  **1.2.0**): `python -m compileall -q src tests` passed;
  `python -m pytest -q tests/test_document_extraction_service.py`
  **50 passed, 0 failed**; `-k smoke_ -s` **3 passed,
  47 deselected**, producing Persian TXT/PDF/DOCX outputs.
  The local workspace copied the DI/bootstrap components of the
  repository but used a minimal ML-provider import stub to keep Stage-3
  tests isolated; this is NOT a complete Stage 1/2 regression execution.
- **Not Run**: `python -m pytest -q` on the complete HEAD and
  pypdf >=6.21.2; `python -m pip check` on updated Windows environment;
  real-world Persian PDF with embedded font; live HTTP regression on this
  stage. The last recorded full Windows run on Stage 2 was **36 passed**
  with a successful user-reported CPU inference and an earlier HTTP 200
  liveness verification on port 8001; preserve that historical result.
- Known issues: pypdf text ordering depends on font mappings and PDF
  geometry; no OCR; image-only input yields no-extractable-text. Complex
  DOCX drawing elements are not supported. The sandbox cannot fetch the
  current dependency wheels or clone the full remote checkout.
- Commit SHA: recorded in GitHub commit history (cannot include its own
  hash in the commit's tracked file).
- Stage 4 readiness: architecture/API are ready; Stage 3 can be marked
  **Completed** after a full Windows dependency, regression and extraction
  smoke verification, including a genuine Persian text PDF.
- Sources:
  https://pypi.org/project/pypdf/ ;
  https://pypi.org/project/python-docx/ ;
  https://pymupdf.io/licensing ;
  https://github.com/py-pdf/pypdf/security/advisories ;
  https://python-docx.readthedocs.io/en/latest/api/document.html .

## Stage 3 Follow-up — Windows DOCX Table Regression (2026-10-24)

- User-provided Windows PowerShell validation on `bd60bb6bbe3f85f3a333fb44d701b8e70983d7d2`:
  Python **3.12.10**, `pypdf 6.21.2`, `python-docx 1.2.0`,
  `python -m pip check` **Passed**, `compileall` **Passed**.
  Stage 3: **49 passed, 1 failed**; complete repository suite:
  **85 passed, 1 failed**, one non-blocking StarletteDeprecationWarning;
  all 36 prior Stage 1/2 tests passed.
- Failure: `test_docx_table_and_unicode` expected `کتاب\t۲` but
  saw only `کتاب`. No input data loss in Word file; it was introduced
  by the DOCX table extractor's duplicate-cell detection.
- Root cause: `id(cell._tc)` identifies a temporary lxml wrapper whose
  integer ID may be reused after garbage collection. Distinct table
  cells then appear identical and are silently discarded.
- Minimal fix: retain the underlying `cell._tc` XML elements as values
  in `seen_cells: set[object]`, rather than storing integers returned
  by `id()`. True merged cells are still deduplicated.
- Added regression tests: 3x3 Persian table requiring every distinct
  cell, repeated ten times; and a merged-cell case checking no duplicate
  text. Before the fix, the 3x3 test **failed** in isolated Python 3.13.5
  with missing rows/cells; after the fix, both new tests passed.
- Isolated Linux/Python 3.13.5 verification with `pypdf 5.9.0` and
  `python-docx 1.2.0`: `python -m compileall -q src tests` **Passed**;
  Stage 3 `pytest` **52 passed, 0 failed**; TXT/PDF/DOCX
  smoke tests **3 passed, 49 deselected**. This was an isolated
  workspace, not a complete Checkout / Stage 1/2 regression run.
- Updated files in this follow-up: `src/core/services/summarization/document_extraction_service.py`,
  `tests/test_document_extraction_service.py`, and
  `docs/IMPLEMENTATION_PROGRESS.md`. No dependencies or Stage 1/2
  components changed.
- **Pending before Stage 3 Completed:** user rerun of the complete
  Windows suite (expected 88 collected tests, actual result pending),
  full health smoke on this commit, and a representative genuine
  Persian PDF with an embedded font. Keep Stage 3 **In Progress**.
- Fix commit: consult the following GitHub commit history; a tracked
  file cannot include the SHA of the commit that contains it.

## Stage 3 Follow-up — Windows Post-Fix Verification (2026-10-24)

- Evidence: user-provided Windows PowerShell transcript, checked out at
  `c9d29f3e49f45198f4b1f44e7da5ff24e733e169` with
  `git pull --ff-only origin main` and `git rev-parse HEAD`.
- Target environment: Windows PowerShell, activated project `.venv`,
  Python 3.12.10; `pypdf 6.21.2` and `python-docx 1.2.0`
  were confirmed installed during the immediately preceding Windows run;
  `python -m pip check` previously returned no broken requirements.
- `python -m compileall -q src tests`: **Passed** (no errors).
- `python -m pytest -q tests/test_document_extraction_service.py`:
  **52 passed, 0 failed**, 14.78 seconds.
- `python -m pytest -q`: **88 passed, 0 failed**, 1 non-fatal
  `StarletteDeprecationWarning`, 11.73 seconds. All 36 retained
  Stage 1/2 automated regressions passed.
- `python -m pytest -q -s tests/test_document_extraction_service.py -k smoke_`:
  **3 passed, 49 deselected**, 2.48 seconds. Output confirms TXT,
  synthetic text-layer PDF with Persian ToUnicode mapping, and DOCX
  generated the expected Persian samples.
- DOCX table-cell regression is **resolved** on Windows by retaining
  `cell._tc` XML elements instead of storing `id(cell._tc)`; the
  originally failing Unicode-table test now passes. Both new table
  tests are included in the 52 Stage 3 tests.
- Stage 3 automated tests, DI discovery, compatibility of pinned
  extraction dependencies, and Stage 1/2 regressions: **Verified**.
  The extra warning is third-party and not currently blocking.
- **Not yet verified on this commit:** a representative real-world
  Persian text-based PDF with embedded font and a live Uvicorn
  `GET /api/v1/health` smoke run. The existing automated
  TestClient health and OpenAPI tests pass as part of the full suite,
  and a previous Stage 1 live HTTP smoke passed historically.
- **Status: In Progress** until these remaining independent acceptance
  checks are completed. Do not describe Stage 3 as Completed based
  solely on the synthetic PDF sample. No code changes needed based
  on the latest automated result.
- Next step: perform a real embedded-font Persian PDF extraction
  through `DocumentExtractionService` and recheck live HTTP health;
  record results, then mark Stage 3 Completed if acceptable.

## Stage 3 Follow-up — Real Persian PDF RTL Extraction (2026-10-24)

- Evidence: user-selected real text-layer PDF at a local Windows Downloads path
  was opened successfully through `DocumentExtractionService.extract(...)`;
  **1,896 characters** were returned, but text order was incorrect.
  Examples: `یسراف نتم` instead of `متن فارسی`,
  `یعونصم شوه` instead of `هوش مصنوعی`, and
  `هنومن دنس` instead of `سند نمونه`.
  The filename and absolute user path are intentionally not committed.
- Root cause: PDF generators can store Persian glyphs in visual rather than
  logical order. The existing pypdf `layout` extractor exposed visual order.
  pypdf `plain` can fix some RTL words but has different risks with
  mixed scripts, numbers and separators; a global mode replacement is unsafe.
- Scope-limited code fix: for extracted PDF text, build visual-to-logical
  candidate lines by reversing token order and RTL grapheme clusters while
  preserving standalone numbers and Latin tokens. A conservative score of
  common Persian words chooses corrections only with positive linguistic
  evidence, and prioritizes per-line evidence to avoid reversing already
  logical lines. No OCR, model calls, HTTP types or new dependencies added.
  TXT/DOCX, constructor DI and Stage 1/2 source remain unchanged.
- Known limitation: PDF RTL restoration is heuristic, not a full Unicode
  bidirectional layout reconstruction. Very short ambiguous text, arbitrary
  mixed-direction inline spans, unusual ligatures/fonts and malformed
  ToUnicode maps may still be inaccurate; compare against real documents.
- Added five PDF regression tests: visual-order Persian heading,
  visual-order RTL with Persian/Latin numbers, mixed-order lines,
  mixed-order pages and unchanged English extraction.
- Isolated Linux/Python **3.13.5** validation with **pypdf 5.9.0**,
  **python-docx 1.2.0** and an isolated ML-provider stub:
  `python -m compileall -q src tests` **Passed**;
  `python -m pytest -q tests/test_document_extraction_service.py`
  **57 passed, 0 failed**;
  three smoke cases **3 passed, 54 deselected**.
  Additionally, an in-memory PDF generated using WeasyPrint and a real
  Persian-capable embedded font reproduced backwards `layout` output
  before the fix. After the fix, extraction verified correct
  `سند نمونه • متن فارسی`, `آشنایی کوتاه با هوش مصنوعی` and
  `سال ۱۴۰۵ و 2026` without losing the Persian or Latin numbers.
  The WeasyPrint-only fixture/dependency is **not** committed.
- **Not Run:** complete post-change 93-case repository regression on Windows,
  compatibility of this change against user's installed pypdf 6.21.2,
  re-extraction of the user's exact PDF, and live Uvicorn health smoke.
  Previous Windows `88 passed` result belongs to the prior commit only.
- Changed files: `src/core/services/summarization/document_extraction_service.py`,
  `tests/test_document_extraction_service.py`, `README.md`, and
  `docs/IMPLEMENTATION_PROGRESS.md`.
- **Stage 3: In Progress.** Retest the user's original PDF after pulling
  latest `main`, run all tests, verify live HTTP health; only then reassess
  completion and Stage 4 readiness.
- Documentation: https://pypdf.readthedocs.io/en/stable/modules/PageObject.html .

## Stage 3 Follow-up — Windows RTL Fix Validated with Real PDF (2026-10-24)

- Evidence: user-supplied Windows PowerShell output after fast-forward
  checkout of `faf02694a405b5b512fd206a28df1f3b422b377d`
  (`fix: recover visual-order Persian text from PDFs`).
- Environment: Windows PowerShell, project `.venv`, Python 3.12.10;
  dependencies `pypdf 6.21.2` and `python-docx 1.2.0` verified
  on the same machine during the prior dependency installation.
- `python -m compileall -q src tests`: **Passed**, no reported errors.
- `python -m pytest -q tests/test_document_extraction_service.py`:
  **57 passed, 0 failed**, 18.74 seconds.
- `python -m pytest -q` (complete repository regression):
  **93 passed, 0 failed**, 1 non-blocking `StarletteDeprecationWarning`,
  19.04 seconds. All retained Stage 1/2 tests also passed.
- Real Persian text PDF: user ran
  `DocumentExtractionService().extract(p.read_bytes(), p.name)`
  successfully, producing **1,136 extracted characters** on this
  commit, compared with 1,896 reported prior to the RTL fix.
  Correct logical-order examples now include
  `سند نمونه • متن فارسی`, `آشنایی کوتاه با هوش مصنوعی`,
  `هوش مصنوعی چه کاربردهایی دارد؟`, and readable Persian paragraphs.
  The difference in character counts is observed but not fully
  explained or independently verified as lossless; some original
  lines had very large amounts of PDF layout whitespace.
- Important **known quality limitation**: this same real-world PDF
  still includes text/glyph anomalies such as `سالمت` versus
  `سلامت`, `اطالعات` versus `اطلاعات`, `مسئوالنه` versus
  `مسئولانه`, and absent joining/spacing in some words. These may
  arise from ToUnicode/font maps, PDF shaping, the heuristic or a
  combination; no unsupported root-cause assertion is made.
  Stage 3 guarantees extraction of usable text from text-layer PDFs,
  **not lossless full-fidelity reconstruction for every PDF**.
- The real PDF is stored only on the user's local machine;
  its bytes were not uploaded or committed. Automatic tests verify
  synthetic cases separately; the real sample is validated by
  inspecting the user's pasted output.
- **Not Run on this commit:** live Uvicorn GET /api/v1/health smoke
  outside TestClient (automated health tests pass). A specific
  fidelity regression test against the original user PDF is not
  possible until the file itself is available in a safe test fixture.
- Technical decision: no additional parser dependency or
  speculative global text-normalization patch; retain known
  font-specific fidelity issues for targeted follow-up/quality work.
- Changed file in this follow-up: `docs/IMPLEMENTATION_PROGRESS.md`
  only; no changes to model, DI, extraction implementation, or
  dependency constraints.
- **Stage 3 status: In Progress**, pending the agreed independent
  live health smoke and final assessment of the font-specific PDF
  fidelity limitations. Stage 4 code not started.

## Stage 3 Final Acceptance — Windows Live HTTP Health (2026-10-24)

- **Status: Completed.** Acceptance criteria from
  `IMPLEMENTATION_PLAN.md` were reviewed against the current implementation
  and the user's actual Windows test outputs. Stage 4 is **Not Started**.
- User confirmed a fast-forward checkout of progress commit
  `fd6e996ae75a8e5f6aec2db5afb89a2e526bc29a`, then launched
  `python -m uvicorn src.host.app:app --host 127.0.0.1 --port 8001`
  with `env_type=development` and the project virtual environment.
- **Live HTTP smoke: Passed.** Uvicorn logged
  `Application startup complete` and
  `GET /api/v1/health HTTP/1.1" 200 OK`.
  The response body was not copied in this particular log; the HTTP 200
  status and completed startup are verified. Earlier automated health
  checks verified the JSON contract, and a separate Stage 1 live run
  previously observed the endpoint.
- Windows/Python 3.12.10 automated verification on extraction code
  commit `faf02694a405b5b512fd206a28df1f3b422b377d`:
  `compileall` **Passed**; **57/57 Stage 3 tests passed**;
  **93/93 full repository tests passed**; 1 non-blocking third-party
  `StarletteDeprecationWarning`; the three TXT/PDF/DOCX smoke tests
  had also passed on the preceding implementation baseline.
  Subsequent two commits changed `docs/IMPLEMENTATION_PROGRESS.md`
  only, not runtime/test source.
- Real-world Persian PDF: **usable text successfully extracted**, with
  correct logical-order titles and paragraphs after the RTL correction.
  Preserve the **known non-blocking quality limitation**: select glyphs,
  joining and spacing may be inaccurate (e.g. `سالمت`, `اطالعات`),
  and full document-faithful reconstruction is not guaranteed.
  No claim is made that extracted text is character-perfect for every PDF.
- TXT UTF-8/BOM, PDFs including encrypted, malformed and no-text cases,
  DOCX including Unicode tables/merged cells, format validation,
  controlled extraction exceptions, in-memory processing, resource
  guards, and absence of OCR claims are covered by implementation and
  tests. The service remains independent of FastAPI UploadFile and
  does not persist inputs.
- **Changed files for this acceptance follow-up:**
  `docs/IMPLEMENTATION_PROGRESS.md` only. **New dependencies: none.**
- **Passed:** Windows compile, Stage 3 unit/integration suite,
  full regression, real-world PDF usability verification and live HTTP
  health smoke.
- **Failed:** 0 in the reported automated test runs.
- **Not Run:** exhaustive PDF font/glyph accuracy benchmark,
  OCR/scanned PDF processing (outside MVP), model summarization
  endpoint (future stage) and Stage 4 chunking tests (not implemented).
- **Stage 4 readiness: Ready.** Implement token-aware chunking and
  hierarchical summarization only upon a separate Stage 4 request.
- Completion documentation commit SHA is available from GitHub history;
  the SHA of a commit cannot be embedded in its own tree contents.


## Stage 4 — Token-aware Chunking and Hierarchical Summarization (2026-10-24)

- **Status: Completed (Windows acceptance verified 2026-10-24).**
  Initially 47 mocked tests passed in an isolated Python 3.13 workspace;
  independent Windows/Python 3.12.10 verification later passed all
  140 tests and real mT5 smoke. See the final acceptance record below.
- Baseline verified at Stage 4 start:
  f4cf5f8201234ad43243ec361f162b29c86fff3a. Main branch write access
  confirmed. Latest implementation/documentation commits are in GitHub
  history; the SHA of this progress-tracking commit cannot appear in its
  own file content.
- Created: src/core/services/summarization/text_chunking_service.py;
  src/core/services/summarization/long_text_summarization_service.py;
  src/infrastructure/ml/smoke_mt5_long_text.py;
  tests/test_text_chunking_service.py;
  tests/test_long_text_summarization_service.py;
  tests/test_mt5_stage4_provider.py.
- Updated: src/infrastructure/ml/mt5_model_provider.py (public, safe
  tokenizer-only input counter; configurable per-call generation max);
  README.md; docs/IMPLEMENTATION_PROGRESS.md.
- New third-party dependencies: **none**. Base and development model
  configurations unchanged. Model checkpoint/revision stays pinned to
  nafisehNik/mt5-persian-summary at
  b575560ad967050e77a40f907abb1ebbeefb9a15. Existing lazy model
  initialization, DI singleton, inference lock and async thread offloading
  remain intact.
- Provider contracts: count_input_tokens(text: str) -> int counts
  configured tokenizer input IDs including specials after provider-style
  edge trim, initializing tokenizer without weights; read-only public
  max_input_tokens, max_input_characters and max_output_tokens properties;
  summarize(text, *, max_output_tokens=None) and summarize_async with the
  same optional keyword, preserving existing one-argument calls.
- TextChunkingService constructor injects Mt5ModelProvider. Public
  normalize(text), fits(text), and chunk(text) implement exact
  tokenizer-derived chunk validation. Chunk concatenation reconstructs
  normalized text, never silently discarding document tails. Normalization
  folds newline styles, collapses horizontal whitespace, reduces 3+ newlines
  to two and trims outer whitespace; original whitespace is not
  character-for-character preserved. Paragraph/sentence/word boundaries
  preferred; forced character splits permitted if required. Empty, invalid
  and over-budget text produce typed errors.
- LongTextSummarizationService injects TextChunkingService and
  Mt5ModelProvider. summarize_async(text, summary_length='medium')
  maps, combines in source order, recursively reduces, validates each
  model input, and performs final generation within the requested budget.
  output_token_budget maps short: 40; medium: 80; long: 120 given the
  existing config max_output_tokens=120. These are Transformers decoder
  max_length ceilings, not character/word counts; the output is checked
  again by re-encoding with the tokenizer. No blind substring slicing
  is used.
- Operational controls: at most 200,000 normalized document characters,
  64 chunks per chunking pass, 6 hierarchy levels, 128 model calls per
  request. Require at least 5% character reduction for each map/reduce
  iteration; insufficient progress, resource exhaustion or model errors
  fail explicitly. These are conservative application budgets, not the
  checkpoint's published maximum capacity. Model calls are sequential
  within a request and provider inference is serialized per process;
  tokenization and inference are dispatched to worker threads in the
  async service. Cancellation cannot preempt an already-running model
  call in a thread.
- Quality caveat: hierarchical summaries can omit semantic details
  despite complete source coverage by chunking. PDF extraction's
  previously documented RTL/font/glyph limitations remain unchanged.

### Stage 4 Test Commands and Results

Source-only Linux/Python 3.13.5 isolated workspace with the Stage 4
source/tests and a reconstructed subset of baseline DI/config components:

~~~bash
python -m compileall -q src tests
python -m pytest -q tests/test_text_chunking_service.py tests/test_long_text_summarization_service.py tests/test_mt5_stage4_provider.py
~~~

- Compile: **Passed**.
- Stage 4 tests: **47 passed, 0 failed**. Coverage includes tokenizer
  specials, exact boundary/overflow, Persian ZWNJ, long unpunctuated
  input, mixed scripts/numerals, normalization, chunk order/full
  normalized coverage/tail retention, char and chunk count limits,
  hierarchy direct/multistage paths, requested length tiers,
  empty/error outputs, no-progress/depth/call limits, non-blocking async
  execution, constructor DI graph and lazy tokenizer-only loading.
- GitHub uploaded blob SHAs for the two core services, all three test
  files and the long-text smoke script were checked against Git blob
  hashes of their locally verified source files; they match.
  Provider was modified against GitHub's existing file using targeted
  substitutions rather than copied from the isolated local variant.
- **Not Run** in this environment: full 93-case Stage 1–3 regression
  against the final GitHub checkout; tests on Windows/Python 3.12.10;
  real pinned-checkpoint CPU smoke; live Uvicorn health on the new HEAD;
  production performance or memory measurements. No model weights were
  downloaded. Do not conflate the prior 93 passing Windows tests on
  Stage 3 with verification of this Stage 4 revision.
- Known non-blocking issues: conservative hierarchy may reject long,
  uncompressible text; some generated text can expand when re-encoded
  and trigger a typed output-limit error; a CPU run may take substantial
  time and RAM. A non-blocking Starlette deprecation warning appeared
  in the prior Windows Stage 3 suite.

### Stage 4 Pre-Acceptance Checklist (historical; verified below)

- Run pip check, compile, new Stage 4 tests, all regression tests and
  opt-in real smoke on Windows after git pull --ff-only origin main.
  Confirm nonempty generated Persian summary, acceptable token length,
  and no new regression failures. Stage 4 must stay **In Progress**
  until those acceptance checks succeed, or their environment blockers
  are explicitly accepted. The implementation is ready for verification;
  Stage 5 should start only after Stage 4 final acceptance.

## Stage 4 Final Acceptance — Windows Python 3.12.10 (2026-10-24)

- **Status: Completed.** User-provided Windows PowerShell validation was run on
  clean `main`, HEAD `9aa9a963f4b5df34908b09efe806bd262b146369`,
  already current with `origin/main`. `git status --short` returned no local changes.
  Only this progress document changes in the acceptance follow-up.
- Environment: Windows PowerShell, project-local `.venv`, Python **3.12.10**,
  `env_type=development`. The shell initially activated a different project's
  venv but explicitly activated this repository's `.venv` before tests.
- Dependencies: `python -m pip install -r requirements.txt` reported requirements
  satisfied, including Transformers 4.57.6, Torch 2.14.1+cpu,
  SentencePiece 0.2.2, pypdf 6.21.2 and python-docx 1.2.0.
  `python -m pip check`: **Passed** (`No broken requirements found.`).
  No dependency changes.
- `python -m compileall -q src tests`: **Passed**.
  `bootstrap_di(); resolve(LongTextSummarizationService)` worked and
  `output_token_budget` for short/medium/long returned **[40, 80, 120]**.
- Stage 4 automated test command:
  `python -m pytest -q tests/test_text_chunking_service.py tests/test_long_text_summarization_service.py tests/test_mt5_stage4_provider.py`:
  **47 passed, 0 failed in 11.13s**.
- Complete regression `python -m pytest -q`: **140 passed, 0 failed in 15.77s**;
  one non-blocking `StarletteDeprecationWarning` in third-party
  `fastapi.testclient`. This includes all prior 93 tests and 47 new Stage 4 tests.
  A separate, redundant second `pytest` invocation ended with
  `KeyboardInterrupt` during pytest import, before test execution;
  it is **not a failed test** and does not invalidate the preceding complete run.
- Real CPU smoke `python -m src.infrastructure.ml.smoke_mt5_long_text`:
  completed without an exception traceback, showing
  `Input characters: 3184`, `Summary token budget: 80` and nonempty
  Persian summary `برای تحلیل اسناد فارسی نیاز دارد.`.
  The smoke asserts the input spans multiple chunks and final output,
  re-encoded by the actual tokenizer, stays within the requested budget.
  **Functional smoke passed**; this does not measure summary quality,
  throughput or RAM.
- Live health via `python -m uvicorn src.host.app:app --host 127.0.0.1
  --port 8001`: startup completed and `GET /api/v1/health` returned
  **HTTP 200 OK**.
- Non-blocking observations: legacy T5 tokenizer behavior;
  HF Xet fallback to regular HTTP because `hf_xet` is absent;
  Windows Hugging Face cache symlink warning; an approximately
  1.20 GB `model.safetensors` download progress shown around the smoke
  even though current Provider explicitly uses `use_safetensors=False`
  for model loading. The origin of this extra transfer is unverified.
  The brief/generic summary for the repeated synthetic text is not evidence
  of consistent real-document fidelity; quality evaluation remains pending.
  PDF RTL/font fidelity limitations from Stage 3 remain.
- **Passed:** dependency consistency, compile/import, DI graph, length mapping,
  all 47 Stage 4 tests, all 140 regressions, opt-in real-model smoke,
  and live HTTP health. **Failed: 0** among completed tests.
  **Not Run:** broad representative-document semantic quality benchmark,
  systematic inference latency/RAM profiling, production concurrent-worker
  load test. Those activities are not Stage 4 acceptance blockers.
- **Acceptance decision:** Stage 4 criteria are met in the reported
  Windows environment. **Stage 4 Completed; Stage 5 Ready.**
  No Stage 5 implementation was added. This documentation-only commit's
  SHA is recorded in GitHub history rather than embedded in its own file.



## Stage 5 — Main SummarizationService & Multi-Document Orchestration (2026-10-24)

- **Status: Completed** (final Windows/Python 3.12.10 acceptance verified
  from the user's run logs on 2026-10-24; see acceptance record below).
- **Starting HEAD:** af10d02b798b1fe8ae43e5526f51204e834c70f1.
  Repo owner Amirmahdimtz; main; GitHub connector confirmed push permission,
  current branch head and unprotected status before implementation.
- **Created:** src/core/services/summarization/summarization_service.py,
  tests/test_summarization_service.py.
- **Updated:** README.md, docs/IMPLEMENTATION_PROGRESS.md.
- **Third-party dependencies:** none. Previous Stage 1–4 files, model
  provider, configuration and DI registration are unchanged.
- **Service contract:** constructor-injected DocumentExtractionService and
  LongTextSummarizationService with @inject auto-discovery.
  summarize_text_async(text, summary_length="medium") -> TextSummaryResult;
  summarize_file_async(content, filename, summary_length="medium")
  -> FileSummaryResult on success, typed exception on failure;
  summarize_files_async(files: Sequence[DocumentInput],
  summary_length="medium") -> MultiFileSummaryResult.
  Results are immutable slotted dataclasses.
- **Metadata:** actual character counts only, raw input length for text
  and extracted Unicode length for files; no fabricated token counts,
  model ID or chunk counts. Characters, words and encoded tokens differ.
- **Error policy:** empty/invalid text and summary length are rejected
  before inference; empty model output is an explicit ModelInferenceError.
  A single file propagates Stage 3 / Stage 4 typed exceptions.
  In a batch, known document/parser/chunking/model errors become
  per-file failure entries with exception-class error_code and safe,
  fixed error_message without document or internal exception text.
  Invalid collection or size is a SummarizationRequestError; an invalid
  summary length is SummarizationInputError for the whole batch.
  Programming exceptions and asyncio.CancelledError propagate.
- **Partial success:** ordered tuple retains every position, including
  duplicate filenames; succeeded/failed counts are derived. Each batch
  processes at most 32 documents sequentially and snapshots the input
  sequence. No unbounded tasks, no persistence or upload/HTTP types.
  Stage 3 extraction is offloaded to asyncio.to_thread. Stage 4 retains
  its existing tokenizer, inference, hierarchy and resource limits.
- **Local source-only verification:** Python 3.13.5 Linux isolated
  workspace using the new service and tests plus locally reconstructed
  fake interfaces for existing Stage 1–4 dependencies.
  python -m compileall -q src tests: Passed.
  python -m pytest -q tests/test_summarization_service.py:
  **60 passed, 0 failed**.
  Includes invalid text/length/bytes, long delegation, per-format extraction
  orchestration, typed parser/model/resource errors, duplicate filenames,
  partial/all failures, error-message redaction, cancellation, sequential
  inference, event-loop responsiveness and collection mutation.
- **Historical pre-Windows verification (superseded below):** Stage 5 tests against the *entire*
  latest repository checkout, complete Stage 1–5 pytest regression on
  Windows/Python 3.12.10, bootstrap_di/resolve on a real Stage 5 checkout,
  real-parser Stage 5 integration and real-model Stage 5 smoke.
  The GitHub integration exposes repository source and commits but this
  sandbox cannot clone GitHub directly (DNS unavailable). Do not claim
  the previous 140 Stage 4 tests constitute Stage 5 regression verification.
- **Failed tests:** none in the isolated Stage 5 run; full checkout outcome
  is unknown. Prior baseline: 140 passed on Windows for Stage 4.
- **Known issues:** a cancelled thread-offloaded parser or inference can
  continue until its blocking function returns; total concurrency across
  independent requests is outside this per-request batch limit.
  Stage 6 must enforce stream upload and payload limits before bytes reach
  this service. Model quality, PDF RTL/font accuracy and latency/RAM
  benchmarks remain open from previous stages.
- **Commit message:** feat: implement main summarization service and multi-file orchestration.
  Commit SHA is obtainable from GitHub history; it cannot be embedded in
  the same commit's tracked progress file.
- **Stage 6 readiness:** Ready. Final Windows/Python 3.12.10 acceptance is
  recorded below; Stage 6 may add the HTTP DTO/controller/upload boundaries.


## Stage 5 Final Acceptance — Windows Python 3.12.10 (2026-10-24)

- **Stage status: Completed.** User-supplied PowerShell verification was run
  from the project root on a clean working tree with the project-local
  .venv and env_type=development. git pull --ff-only origin main advanced
  af10d02..d3ac76d; git rev-parse HEAD confirmed
  d3ac76daf5de4a139e1e09265002eb92effbe1fe.
  The implementation commit was:
  "feat: implement main summarization service and multi-file orchestration".
  No Stage 5 source, test, provider, DI, configuration or dependency changes
  were needed for this documentation-only acceptance follow-up.
- **Environment:** Windows PowerShell, Python 3.12.10, project .venv.
  Requirements were already satisfied; python -m pip check reported
  "No broken requirements found." before and after dependency installation.
- **Passed — compile and DI:** python -m compileall -q src tests,
  Stage 5 public-contract import, bootstrap_di() and
  resolve(SummarizationService). All completed without error.
- **Passed — Stage 5 tests:**
  python -m pytest -q tests/test_summarization_service.py
  => **60 passed in 10.55s; 0 failed**.
- **Passed — full regression:**
  python -m pytest -q
  => **200 passed, 1 warning in 28.98s; 0 failed**.
  This includes the prior 140 Stage 1–4 tests and 60 Stage 5 tests.
  The single non-blocking StarletteDeprecationWarning originates in the
  third-party fastapi.testclient httpx/starlette compatibility layer.
- **Passed — real-parser integration:**
  python -m pytest -q -s tests/test_document_extraction_service.py -k smoke_
  => **3 passed, 54 deselected in 9.10s**.
  The three smoke cases printed extracted Persian TXT, text-PDF and DOCX.
  An earlier malformed selector invocation (-k smoke_.) was interrupted
  by KeyboardInterrupt while importing pytest; this was not a test
  assertion failure and the corrected invocation passed.
- **Passed — real mT5 multi-file orchestration functional smoke:** with
  bootstrap_di()/resolve(SummarizationService), a UTF-8 TXT plus invalid
  PDF were submitted as DocumentInput in a single batch with length short.
  Results: valid.txt => success=True, summary=".", error_code=None;
  invalid.pdf => success=False, summary=None,
  error_code="InvalidDocumentError". Assertions for one success,
  one failure and nonempty successful summary completed.
  This establishes actual provider/extractor integration and per-file
  isolation on the pinned model, **not useful summary quality**:
  a single punctuation mark is not a meaningful Persian summary.
- **Passed — live HTTP health:** Uvicorn started with
  python -m uvicorn src.host.app:app --host 127.0.0.1 --port 8001;
  GET /api/v1/health returned **HTTP 200 OK**.
  Stage 6 summarization endpoints remain intentionally absent.
- **Failed automated tests:** 0 among completed runs.
- **Not Run:** quantitative/qualitative model evaluation on representative
  Persian documents, production RAM/latency and multi-request load tests,
  OCR, and Stage 6 upload/API endpoints (not implemented).
- **Known issues:** model output can be technically nonempty while
  semantically useless ("." in this real smoke). Do not treat this smoke
  as proof of summary quality; establish quality checks and diagnostics
  during Stage 7 and evaluate representative real documents.
  Existing PDF RTL/font reconstruction limitations remain.
  Cancellation cannot forcibly stop an already-running worker thread;
  upload-stream/body limits belong at Stage 6/7 ingress.
  The observed StarletteDeprecationWarning is non-blocking.
- **Acceptance decision:** Stage 5 business orchestration, bounded
  sequential multi-file processing, typed partial success, auto-discovery,
  actual model invocation, and all requested functional verification
  criteria are satisfied. **Stage 5 Completed; Stage 6 Ready.**
  Quality benchmarking is a follow-up, not a claim of Stage 5 success
  in semantic accuracy.
- **Acceptance commit message:** docs: confirm stage 5 Windows acceptance and stage 6 readiness.
  The acceptance SHA is visible in GitHub history (it cannot be embedded
  into its own commit contents).

## Stage 6 — REST API, DTO and Secure Upload (2026-10-24; implementation / pre-acceptance record)

- **Stage: 6; Status: In Progress** pending final full-repository regression and Windows/Python 3.12.10 acceptance. Stages 1–5 unchanged and previously Completed. Stage 7 Not Started.
- **Starting HEAD:** f82712b9a3c3684c08fc5d2e40eda0ccd7aefc1d on Amirmahdimtz/mT5-Persian-Summary/main, verified via GitHub branch endpoint. Repository push permission: true, `main` reported unprotected; branch-protection detail requires an unavailable GitHub app permission. Repository rulesets collection returned empty.
- **Created:** `src/application/summarization/summarization_controller.py`, `src/application/summarization/dtos/summarization_dto.py`, `src/application/summarization/upload_limit_middleware.py`, `tests/test_summarization_api.py`.
- **Updated:** `src/application/web.py` (safe 422 error handler and pre-multipart upload limit wiring), both `src/host/res/appsettings*.yaml` (aggregate upload budget), `requirements.txt` (python-multipart), `README.md`, this progress file.
- **Dependencies:** `python-multipart>=0.0.18,<1.0` for FastAPI multipart parsing; no new layering or DI registration.
- **Architecture:** `@inject` constructor receives existing `SummarizationService` and `ConfigReader`; `api() -> APIRouter` auto-discovered via existing `WebService`; no duplicated feature/root prefix, no model load at bootstrap, no Core/Provider changes. ASGI ingress limiter belongs to HTTP/Application.
- **Endpoints:** POST `/api/v1/summarization/text` JSON; POST `/api/v1/summarization/file` multipart field `file`; POST `/api/v1/summarization/files` repeated multipart fields `files`. Each accepts `summary_length` in short/medium/long, default medium. Prefix remains configurable via `api.prefix`. OpenAPI `response_model` exposes typed DTOs and documented errors. DTO fields use actual Stage 5 character counts, not inferred model metadata.
- **Validation:** nonblank strict-string text up to 200,000 characters; safe filename basename 1–255 Unicode characters, .txt/.pdf/.docx extension, matching MIME or octet-stream/absent MIME; upload nonempty; 1–32 files; total documents <= configured 32 MiB (valid configurable range 20–64 MiB); per file <= 20 MiB.
- **Ingress/stream policy:** ASGI pre-parser cap of aggregate byte budget plus 1 MiB framing allowance regardless of client Content-Length. A `SpooledTemporaryFile` keeps <=1 MiB wire-body buffer in RAM and may use temporary disk; closed on all exits. After Starlette multipart parsing, `UploadFile.read(n)` is bounded to 64 KiB reads with independent per-file/aggregate counters; resources are closed in finally. No permanent document storage. Batch holds bounded bytes in RAM because Stage 5 accepts `DocumentInput(content: bytes)`.
- **HTTP policy:** sanitized fixed `detail.code/message` for known application errors; 400 (empty/bad upload or malformed multipart); 413 (size/file count/processing budgets); 415 (unsupported media type/extension); 422 (Pydantic invalid JSON/field, parser invalid/unextractable file); 500 (inference/parser unexpected operational failure or empty service summary); 503 (model loading failure). Unexpected programming errors and cancellation are not suppressed. Pydantic default validation response is replaced to avoid reflecting `input` values.
- **Batch partial success:** for a valid upload collection, HTTP 200 for partial or all per-document failures. Per-file error codes are safelisted and messages fixed. The Core-derived `succeeded` and `failed` are preserved; results retain order and duplicate filenames. Request-level validation failures reject the entire batch before inference. No unbounded fan-out.
- **Test commands:** `python -m compileall -q src tests`; `python -m pytest -q tests/test_summarization_api.py`; `python -m pytest -q`; `python -m pip check`; optional real-model API smoke as described in README.
- **Actually executed in isolated Linux/Python 3.13 harness:** `python -m compileall -q` on new Stage 6 files (passed); `python -m pytest -q tests/test_summarization_api.py` using locally reconstructed minimal service/DI modules matching inspected public contracts: **43 passed, 0 failed, 1 warning**. No real model weights downloaded. GitHub blob hashes of new code and tests verified against local Git hashes.
- **Not Run:** test suite against full real GitHub checkout (container cannot resolve github.com for git clone); `python -m pip check` against repository's complete dependency set; full Stage 1–6 regression; Windows/Python 3.12.10 validation; real model through Stage 6 HTTP API; memory/throughput profiling. The historical Stage 5 Windows baseline was **200 passed, 0 failed**; it is not a Stage 6 regression result.
- **Known issues:** Isolated fake-based tests do not prove full checkout integration. Temporary spooling can use disk and may double-buffer wire multipart temporarily; no cross-request admission budget. A real Stage 5 mT5 smoke returned punctuation-only `.` (functional orchestration passed but quality not established). PDF RTL/font extraction is heuristic. Cancellation cannot preempt work already executing in a worker thread. A prior StarletteDeprecationWarning is non-blocking.
- **Commit message:** `feat: implement summarization REST API and secure file uploads`. The GitHub commit SHA must be read from `main` after the commit; it cannot be included in the content of its own commit.
- **Stage 7 readiness:** after Windows full regression, DI/OpenAPI, HTTP smoke and reported acceptance of Stage 6. Stage 6 remains In Progress until those criteria are evidenced.

## Stage 6 Final Acceptance — Windows Python 3.12.10 (2026-10-24)

- **Final status: Completed.** The user provided Windows PowerShell command output from the real GitHub checkout on the project's own `.venv`, with `env_type=development`. These results supersede the pre-acceptance "In Progress" / "Not Run" entries above; those entries remain as historical evidence of what had not been verified at the time of the implementation commit.
- **Validated implementation HEAD:** `15f3cf9b69c0603e302ba62acdf7ef73932693f3`, message `feat: implement summarization REST API and secure file uploads`. `git pull --ff-only origin main` advanced `f82712b..15f3cf9`; `git rev-parse HEAD` exactly matched; `git status --short` printed no changes. GitHub head still matched when these logs were reviewed.
- **Environment:** Windows PowerShell, Python **3.12.10**, project-local `.venv`, `env_type=development`; installation from `requirements.txt` succeeded, adding `python-multipart 0.0.32` within the documented constraint.
- **Dependency integrity:** `python -m pip check` => `No broken requirements found.` **Passed**. `python -m compileall -q src tests` => **Passed** (no errors printed).
- **DI / startup / discovery / OpenAPI:** `bootstrap_di()`, `resolve(SummarizationController)`, `resolve(SummarizationService)`, and the assertion that the resolved `Mt5ModelProvider._model is None` on startup **Passed**. All three POST paths are present in `app.openapi()`, and the existing health route remains present.
- **Stage 6 tests:** `python -m pytest -q tests/test_summarization_api.py` => **43 passed, 0 failed, 2 warnings in 14.35s**. Tests cover valid/invalid inputs, response and HTTP mapping, bounded upload reads, ingress aggregate enforcement, resource cleanup, partial success, cancellation and discovery, using fakes rather than downloading/initiating inference.
- **Full regression:** `python -m pytest -q` => **243 passed, 0 failed, 2 warnings in 40.23s**. Compared with Stage 5's last baseline of 200 passed, the full run contains 43 new Stage 6 tests and no failures.
- **Real document parser smoke:** `python -m pytest -q -s tests/test_document_extraction_service.py -k smoke_` => **3 passed, 54 deselected in 3.95s**. Persian TXT, generated text PDF and DOCX extraction output was displayed.
- **Live ASGI smoke:** `python -m uvicorn src.host.app:app --host 127.0.0.1 --port 8001` started successfully; `GET /api/v1/health`, `GET /openapi.json` and `GET /docs` returned HTTP **200**. OpenAPI displayed exactly the expected health plus summarization text/file/files routes in the user log.
- **Real model HTTP calls:** Persian text POST `/api/v1/summarization/text` with `summary_length=short` returned **200**, `input_characters=1685`, `output_characters=87`, a nonempty `summary` (the PowerShell `Invoke-RestMethod` display showed mojibake, so semantic quality of this particular output cannot be judged from its console rendering). A valid UTF-8 TXT via POST `/file` with `summary_length=medium` returned **200**, `success=true`, nonempty Persian summary and character counts (43 input, 46 output). The same TXT paired with a deliberately invalid PDF via POST `/files` returned **200**, `succeeded=1`, `failed=1`, ordered result records and safe `InvalidDocumentError` for the PDF. Invalid PDF alone returned **422** with sanitized `detail.code/message`. An upload of 20 MiB + 1 byte returned **413** with `FileTooLarge`; test file was removed. Other generated sample files were removed afterwards. Uvicorn request logs corroborated these status codes.
- **Warnings:** nonblocking third-party `StarletteDeprecationWarning` at `fastapi/testclient.py` and `DeprecationWarning` about deprecated `data=` usage in the invalid-JSON test; no failed tests. These are candidates for targeted Stage 7 maintenance and do not invalidate Stage 6 acceptance.
- **Known limitations retained:** PowerShell string rendering of the text API's Persian response was mojibake while `curl.exe` displayed valid Persian JSON for file/batch endpoints; likely client-side response encoding/display and not proof of malformed server-side output. Prior punctuation-only real-model output and the current brief, repetitive summaries do not establish semantic quality. Representative-language evaluation remains Stage 7 work. PDF RTL/font mappings remain heuristic; multipart spooling can use temporary disk; multi-request aggregate memory/CPU admission and throughput profiling are not verified. Cancellation cannot forcibly stop already-running worker threads. No model, Core, provider or generation-parameter change is justified by these acceptance results.
- **Passed:** 43 Stage 6 tests, 243 full-suite tests, 3 real-parser smoke tests, pip check, compilation, DI, discovery, OpenAPI, lazy model loading, live liveness, real text/single/multi-file routes, invalid PDF mapping, partial success and oversized upload protection. **Failed: 0** among executed tests.
- **Not Run:** systematic qualitative mT5 benchmark on real Persian corpora; production multi-request load, RAM/latency profiling, and an isolated live ASGI request that exercises the full aggregate wire-body cap (the aggregate guard was covered in Stage 6 automated tests). These are non-blocking for Stage 6 acceptance and remain Stage 7 hardening tasks.
- **Acceptance decision:** all Stage 6 acceptance criteria are satisfied by the user-provided real Windows test and HTTP evidence. **Stage 6 Completed; Stage 7 Ready.** This follow-up changes only `docs/IMPLEMENTATION_PROGRESS.md`. Its own acceptance commit SHA is available from GitHub history and cannot be embedded in the same commit's contents.

## Stage 7 — Testing, Security & Runtime Optimization (2026-10-24)

- **Status: In Progress.** Do not mark Completed before full regression, installed-dependency verification and real-model Windows/Python 3.12.10 smoke evidence.
- Starting HEAD: `7c40aa1cb975349fcb957701077ad11ffde1a809`; GitHub `main` write permission confirmed.
- Updated: `src/infrastructure/ml/mt5_model_provider.py`, `src/application/summarization/upload_limit_middleware.py`, `src/application/summarization/summarization_controller.py`, `src/application/web.py`, `src/host/res/appsettings.yaml`, `src/host/res/appsettings.development.yaml`, `requirements.txt`, `README.md`, `docs/IMPLEMENTATION_PROGRESS.md`. Added: `tests/test_stage7_hardening.py`, `src/infrastructure/ml/smoke_mt5_quality.py`.
- Verified security finding: `python-multipart>=0.0.18` allowed versions affected by header-parsing DoS (GHSA-pp6c-gr5w-3c5g). Requirement minimum raised to 0.0.27. Existing `pypdf>=6.21.2` remains unchanged; no broad version upgrades. Actual installed distributions have not been inspected in the target environment.
- Inference finding: synchronous `threading.Lock` bounded active generation, but Async `asyncio.to_thread` could create waiting worker threads without admission control; cancelling an await abandoned a still-running thread. Added per-loop Async semaphore, 30-second default bounded queue wait, shielded worker task, completion-based slot release, and configurable process-wide `threading.BoundedSemaphore`. Defaults: `model.max_concurrent_inferences=1`, `model.queue_wait_seconds=30.0`.
- Upload finding: raw ASGI body was bounded independently of `Content-Length` but many parallel requests could retain memory/disk spools. Added `api.upload.max_active_requests=2` per ASGI process (through downstream completion), and `api.upload.idle_timeout_seconds=30`. Capacity exhaustion responds with sanitized HTTP 503; receive inactivity yields sanitized HTTP 408; `finally` closes spool and releases admission. Existing 20 MiB/file, 32 MiB aggregate and body framing budgets preserved.
- Lifecycle: provider stays a lazy-loaded `@inject` singleton per worker, with no additional model downloads per call. No model checkpoint, tokenizer or generation hyperparameters changed; no persistence, queue or new architectural layers.
- Cancellation/timeout boundary: `asyncio.shield` protects the admitted thread-backed task after client cancellation; cancellation does **not** stop active `torch.generate`, tokenization, model loading or synchronous document parser threads. Queue wait and request-body idle timeouts are not hard inference/parser time limits. Unexpected programming errors still propagate, while known model admission failures map to safe HTTP 503.
- Resource assessment (analytical, not measured): one active request can retain the original bounded upload spool, Starlette multipart spool and materialized in-memory `bytes`; two admissions cap this multiplier per process. `uvicorn --workers N` multiplies model weights and admission caps N times. Use one CPU worker until observed RAM and latency permit otherwise. PDF decompression/parser CPU/RAM adversarial behavior is not fully sandboxed.
- Added deterministic mock-only capacity, cancellation, cross-loop, upload-timeout and 503 redaction tests. Created a separate optional three-sample Persian quality smoke (short, long, multitopic); reports output and heuristics. No claims of improvement in factual correctness or ROUGE.
- **Verification at commit preparation:** Final-checkout `python -m pip check`, `python -m compileall -q src tests`, `python -m pytest -q tests/test_stage7_hardening.py`, `python -m pytest -q`, real model quality smoke, RAM/CPU/GPU measurements: **Not Run** (execution sandbox could not resolve github.com to clone the full current repository). Historical Stage 6 Windows regression: **243 passed**, not evidence that Stage 7 passes. No Stage 7 test result is represented as Passed.
- Known issues: pending Python 3.12.10 Windows acceptance; no real inference concurrency/load benchmark; parser threads are not preemptible, PDF resource usage still needs process isolation under hostile inputs; optional model quality heuristic is not an objective reference metric.
- Commit message: `feat: bound inference and upload concurrency with cancellation safety`; exact SHA is the subsequently verified GitHub commit, not embedded in this same tracked content.
- Stage 8 readiness: Stage 7 hardening changes prepared; formal Stage 7 completion and Stage 8 final delivery remain blocked on acceptance evidence.

### Stage 7 GitHub commit verification (2026-10-24)

- Implementation commit SHA: `6904e83d12865a5d8cea6788f5867b46760d4c51` — `feat: bound inference and upload concurrency with cancellation safety` (11 Stage 7 files).
- Test correction commit SHA: `65dfe06a74987835b43bb306dffc883c445c9167` — `test: use awaited ASGI send callbacks in concurrency tests` (required by the ASGI send callable contract).
- Upload admission follow-up SHA: `60d4e38b338719b1349948fdb0f3637a71305a04` — `fix: enforce upload admission across ASGI event loops` (replace loop-bound Async semaphore with process-wide `threading.BoundedSemaphore` plus non-blocking async polling).
- All three changes were verified as commits on GitHub `main`; final branch head advances again with this progress-document update. GitHub branch history is the authoritative reference.
- No complete checkout or installed target dependencies were available to execute the new Python tests in the tool sandbox. Do not infer Passed results from successful GitHub commit creation.

## Stage 7 Acceptance Follow-up — Windows/Python 3.12.10 (2026-10-25)

- **Final Stage 7 Status: Completed** for the scoped testing/security/runtime-hardening acceptance criteria. Stage 8 remains Not Started. The earlier Stage 7 sections describe the pre-acceptance state at their respective dates; this follow-up supersedes their pending-verification status.
- User confirmed clean fast-forward to implementation/verification HEAD `bdb8f63479ac532562a7f70de9751c946f11daf4` (`git status --short` initially empty). `env_type=development` and Python `3.12.10` in `.venv`.
- `python -m pip install -r requirements.txt`: succeeded; installed `fastapi 0.162.0`, `pydantic 2.14.1`, `httpx 0.28.1`, `transformers 4.57.6`, `torch 2.14.1+cpu`, `pypdf 6.21.2`, `python-docx 1.2.0`, `python-multipart 0.0.32`. Dependency minimum `python-multipart>=0.0.27` met.
- `python -m pip check`: Passed (`No broken requirements found`). `python -m compileall -q src tests`: Passed (no errors).
- `python -m pytest -q tests/test_stage7_hardening.py`: **17 passed, 0 failed, 1 non-blocking warning** (10.31 s). Includes mock/deterministic inference and upload concurrency, cancellation and safe HTTP responses; this does not measure live concurrent model RAM/latency.
- `python -m pytest -q tests/test_mt5_model_provider.py tests/test_mt5_stage4_provider.py tests/test_summarization_api.py`: **76 passed, 0 failed, 2 warnings** (14.92 s).
- `python -m pytest -q -s tests/test_document_extraction_service.py -k smoke_`: **3 passed, 54 deselected** (3.64 s), with real Persian TXT/PDF/DOCX parser output.
- `python -m pytest -q`: **260 passed, 0 failed, 2 non-blocking warnings** (21.86 s), versus historical Stage 6 243 passed. Warnings: `StarletteDeprecationWarning` for TestClient `httpx`, and `DeprecationWarning` for HTTPX `data=` raw content; no dependency upgrade justified solely by these warnings.
- Real CPU mT5 quality smoke was run separately on the target Windows environment for all three built-in samples: `--sample short`: 153 source chars -> 74 summary chars; `--sample long`: 5112 -> 63; `--sample multitopic`: 434 -> 93. All reported `nonempty=True`, `persian=True`, `punctuation_only=False`, and `very_short_relative_to_source=False`, with no runtime failure. `T5Tokenizer` legacy warning expected; generation defaults unchanged.
- **Quality finding (not a runtime acceptance failure):** The long sample is an 18-fold repetition and yielded a very compressed 63-char summary, omitting source details; not representative of distinct-topic long documents. The multitopic summary omitted healthcare/education content and **reversed meaning** from source `کاهش آلودگی هوا` (reduce air pollution) to summary `برای افزایش آلودگی هوا` (increase air pollution). Existing string/script/length smoke heuristics cannot establish factual faithfulness. Record as a real model-quality limitation for future evaluation (separate from Stage 7 infrastructure), not proof of a tokenizer/API bug; no model changes or fine-tuning were introduced.
- Live Uvicorn `--workers 1` started successfully. `GET /api/v1/health`, Swagger `/docs` and `/openapi.json`, real JSON text summarization and valid TXT upload returned HTTP 200. Deliberately invalid PDF returned HTTP 422 with sanitized `InvalidDocumentError`. The PowerShell `Invoke-RestMethod` response showed mojibake, but the same server returned correct UTF-8 Persian text through `curl.exe`; do not classify this as a server Unicode regression without evidence.
- Resource observation: `Get-NetTCPConnection` associated listening port 8001 with Python PID 14936; `Get-Process` at the sampled time reported PID 14936 RSS **1046.2 MiB** and another Python PID 19260 RSS **4.1 MiB**. This is a single working-set snapshot after inference, **not peak RAM, cumulative memory growth, a concurrency benchmark, or a per-model allocation measurement**.
- Passed: 260 full-suite tests, 17 focused hardening tests, 76 selected model/API tests, 3 parser smoke cases, 3 real-model smoke runs, dependency health/compilation, real HTTP smoke endpoints. Failed: **0 reported**. Skipped/deselected: **54 deselected** in parser smoke selection (not full-suite skips). Not Run: controlled live multi-request load/peak-RAM profiling, GPU measurements, and adversarial PDF resource exhaustion testing. Unit concurrency coverage is verified, but live performance capacity is not quantified.
- Residual constraints: inference/parser threads cannot be forcibly stopped upon cancellation; admission limits are process scoped; one CPU worker is recommended until representative load profiling; summary factual consistency is not guaranteed. None invalidates the Stage 7 scoped testing and hardening acceptance just verified; surface limitations explicitly in Stage 8 documentation.
- **Stage 8 Readiness:** Ready to begin separately on request. Stage 8 must retain the reported semantic-quality and operational resource limitations; no Docker, model replacement, persistence, or UI was implemented as part of this acceptance follow-up.
- GitHub acceptance commit message: `docs: confirm stage 7 Windows acceptance and stage 8 readiness`. Actual commit SHA is verifiable on the branch after this documentation update (cannot self-reference its own final SHA).

## Stage 8 — Docker, Documentation & Final MVP Delivery (2026-10-25)

- **Status: In Progress**, not Completed. The source and documentation deliverables are committed to `main`, but Docker Build, Docker container startup, Docker HTTP E2E and a post-change full regression have **not** been executed in the available environment. A new live-model Stage 8 E2E result must not be inferred from Stage 7 acceptance.
- GitHub repository: `Amirmahdimtz/mT5-Persian-Summary`, branch `main`; baseline `ba1db6f7272c0ee41856697058904eb455b7b863`. Authenticated GitHub repository permissions reported `admin=true`, `push=true`; the baseline was verified against the latest commit list before Stage 8 writes. No intervening Stage 7 source changes were found.
- **Added:** `Dockerfile` (Python 3.12.10 slim, Linux CPU-only PyTorch index, dependency layer, UID 10001 non-root, healthcheck, one Uvicorn worker); `.dockerignore` (exclude .venv/.git/caches/model assets/sensitive local files); `compose.yaml` (one API service, persistent HF cache, loopback port, init and provisional resources); `tests/test_stage8_delivery.py` (five deterministic packaging/HTTP contract checks); `tests/e2e_http_smoke.py` (opt-in real live HTTP/model smoke with generated TXT/PDF/DOCX, all three lengths, batch, invalid PDF, filename and optional oversized file).
- **Updated:** `README.md` (complete local Windows/Linux, Docker and Compose instructions; cache/permissions/offline/lazy model lifecycle, Swagger and API/response/curl examples, limits/errors, testing/troubleshooting/security/quality/backlog); `docs/IMPLEMENTATION_PROGRESS.md` (this record and Stage 8 status). Existing model/provider/controller/DI/config/source runtime and generation settings **unchanged**. **New Python dependencies: none**. Existing `requirements.txt` uses compatible version ranges, not a reproducible lockfile.
- Docker model cache: `HF_HOME=/home/app/.cache/huggingface` writable by UID 10001 and persisted by named volume; first inference downloads tokenizer/checkpoint, not process startup. Model ID `nafisehNik/mt5-persian-summary`, pinned revision `b575560ad967050e77a40f907abb1ebbeefb9a15`, model-card MIT license, existing CPU settings. Build does not pre-download approximately 1.2 GB of weights. An uncached offline first inference fails through the existing model-load error path (HTTP 503). Failed initialization is process-cached until restart.
- Existing `/api/v1/health` returns `{"status":"ok"}` independently of inference; Docker HEALTHCHECK is **liveness**, not model readiness. No new `/ready` API or unwarranted model warm-up has been added. Uvicorn runs one worker to avoid model duplication. SIGTERM/graceful shutdown remains runtime best effort, not forced cancellation of `torch.generate` or parser threads.
- Docker/Compose resource defaults: explicit Docker run guidance for `--memory 8g --cpus 2`; Compose `MT5_MEMORY_LIMIT` (default 8g) and `MT5_CPUS` (default 2.0). These are unbenchmarked planning allocations. Source upload guard defaults and inference admission remain unchanged (20 MiB/file, 32 MiB aggregate, 1–32 files, 200k chars, two active uploads, 30s upload idle, one inference, 30s admission wait; detailed bounds in README).
- **Passed in available sandbox (isolated from repository checkout):** `python -m compileall -q /mnt/data/stage8/tests` (both authored Stage 8 test scripts compiled without errors); `yaml.safe_load` parsed the authored Compose file; generated text-layer PDF and DOCX bytes created successfully with installed local parsers; pypdf extracted readable Persian text from the synthetic ToUnicode PDF. These are **file-level checks**, not a complete repository test run, real-model smoke, Docker run or HTTP E2E.
- **Failed tests:** 0 observed in the limited isolated checks. **Skipped:** none reported by those checks. **Not Run:** `python -m pytest -q tests/test_stage8_delivery.py`; `python -m pytest -q`; `python -m pip check` on a complete new Stage 8 environment; `python -m src.infrastructure.ml.smoke_mt5_model`, `smoke_mt5_long_text`, `smoke_mt5_quality --sample all`; `python tests/e2e_http_smoke.py --base-url http://127.0.0.1:8001 --large-upload`; `docker build -t mt5-persian-summary:stage8 .`; container startup, health, real inference and `docker compose up --build -d`. Reason: no local Docker executable, restricted outbound GitHub/Hugging Face access, no complete authenticated local git checkout and transformers dependency absent in the test sandbox. No test labeled Passed on the basis of written test code.
- **Historic evidence only, not new Stage 8 verification:** Windows/Python 3.12.10 Stage 7 `260 passed, 0 failed`; 17 focused hardening, 76 model/API, 3 parser smoke; real CPU short/long/multitopic scripts and live HTTP checks on Stage 7. The 260-case baseline predates adding the five Stage 8 tests.
- **Retained known issues:** actual peak Docker RAM/CPU throughput unmeasured; earlier 1046.2 MiB Windows process working set was not peak; multitopic mT5 smoke omitted topics and reversed pollution reduction to increase; long repetitive sample severely compressed; PDF RTL mapping and malicious-document resource safety are limited; requests cannot immediately abort worker-thread inference/parsing. Single worker and process-scoped admission are not distributed limits. No authentication, OCR, persistence, GPU enablement or quality guarantee.
- **Local acceptance commands:** on Windows `git pull --ff-only origin main`; `$env:env_type='development'`; `python -m pip install -r requirements.txt`; `python -m pip check`; `python -m compileall -q src tests`; `python -m pytest -q`; `python -m src.infrastructure.ml.smoke_mt5_quality --sample all`; start `python -m uvicorn src.host.app:app --host 127.0.0.1 --port 8001 --workers 1`; from another shell `python tests/e2e_http_smoke.py --base-url http://127.0.0.1:8001 --large-upload`; `docker build -t mt5-persian-summary:stage8 .`; run with the documented volume/limits; repeat E2E against port 8000; collect `docker compose ps`, health, logs and observed resource usage. See README for complete commands.
- **Acceptance:** Dockerfile, Compose, cache/resource/permissions strategy, API documentation, opt-in E2E harness and explicit liveness/shutdown contract are implemented. Runtime readiness, three successful Stage 8 live endpoints, regression preservation and Docker E2E are **pending independent verification**. No new required MVP placeholder was introduced or identified in the examined source.
- **Next action:** run the documented post-change full regression, real-model HTTP smoke on Windows/Python 3.12 and actual Docker Build/start/health/E2E on a Docker-enabled machine. Record command output and observed resource/quality limitations; only then decide whether Stage 8 may be marked `Completed`. No further architecture feature development is required merely to perform this acceptance.

## Stage 8 Windows Verification and Docker Download Timeout (2026-10-25)

- **Stage 8 status remains In Progress (Docker verification pending)**. User-provided Windows PowerShell evidence was executed against confirmed GitHub `main` HEAD `af395fb3a43b4e8f8d29896044eecac6c8d0a826`, with Python **3.12.10** in `.venv`. `git pull --ff-only` succeeded; `git rev-parse HEAD` matched; `git status --short` showed only local, untracked `invalid.pdf` and `sample.txt`, untouched by Stage 8 changes.
- **Passed, Windows:** all requirements already installed and `python -m pip check` returned `No broken requirements found`; `python -m compileall -q src tests` succeeded. `python -m pytest -q tests/test_stage8_delivery.py`: **5 passed, 1 non-blocking third-party warning**. `python -m pytest -q tests/test_stage7_hardening.py`: **17 passed, 1 warning**. `python -m pytest -q`: **265 passed, 0 failed, 2 warnings** in 10.85s. Two warnings concerned deprecated Starlette `httpx` TestClient usage and raw HTTPX `data=` usage; neither failed tests.
- **Passed, real CPU mT5 Windows smoke:** `smoke_mt5_model` produced nonempty Persian text; `smoke_mt5_long_text` used 3184 input characters with an 80-token summary budget and generated `برای تحلیل اسناد فارسی نیاز دارد.`; `smoke_mt5_quality --sample all` completed the `short` (153→74 chars), `long` (5112→63 chars), and `multitopic` (434→93 chars) samples. T5 tokenizer's legacy-mode message is nonfatal. Factual faithfulness is **not verified**: the multitopic output still erroneously changed pollution reduction to increase and omitted topics; the repeated long sample was severely compressed. The source summary for `smoke_mt5_long_text` is unusually terse, so passing the shape/budget checks is not a semantic-quality success claim.
- **Passed, real HTTP Windows:** Uvicorn `--workers 1` on `127.0.0.1:8001` started and served `/api/v1/health`, `/docs`, and `/openapi.json` with 200, plus direct text and TXT upload. `python tests/e2e_http_smoke.py --base-url http://127.0.0.1:8001 --large-upload` completed successfully: text at all three length tiers; TXT, generated synthetic text-layer PDF and DOCX; all three batch members; sanitized 422 invalid PDF, 400 unsafe filename, 422 invalid summary tier and 413 oversized upload. Direct manual `curl.exe` file batch failed with exit 26 because `sample.pdf` and `sample.docx` were not present; the synthetic E2E batch subsequently passed. The user's `Invoke-RestMethod` terminal showed mojibake Persian text, while `curl.exe` returned readable Persian JSON: investigate PowerShell client decoding if needed rather than attributing it to the service without evidence.
- **Failed, Docker Build (on initial Stage 8 source):** `docker build -t mt5-persian-summary:stage8 .` failed in the PyTorch dependency-installation step downloading the **196.3 MB** official Linux CPU wheel from `download-r2.pytorch.org`: pip's default **15-second socket read timeout** caused `ReadTimeoutError`, exit code 2. Base Python image, context and earlier Docker build steps completed. The image was therefore not created. `docker run` failed because the local image did not exist (registry pull fallback is unrelated to credentials). No container existed for subsequent `docker inspect` or `docker logs`. HTTP 404 from `127.0.0.1:8000` came from another responding Uvicorn process, **not a running Stage 8 Docker container**. The Docker-target E2E returned HTTP 404 at health as an expected consequence of using the wrong service/port; it did not execute an mT5 container smoke.
- **Minimal follow-up correction committed to GitHub `main`:** `Dockerfile` now declares BuildKit Dockerfile syntax, uses a BuildKit pip cache mount (`/root/.cache/pip`) and **180-second socket timeout with 8 retries** for both dependency-install commands, and removes pip's previous cache-disabling flags. The cache mount is not bundled in the image; this avoids unnecessary repeat downloads of already completed packages. `tests/test_stage8_delivery.py` adds assertions for these settings. `README.md` documents the download failure, safe retry, troubleshooting and alternate host port when `8000` is occupied. No model, Python runtime, YAML limits, API, parser or inference changes. No new dependency or secret. This adjustment is based on the observed network failure; it cannot guarantee network availability or a successful download.
- **Not Run after the follow-up Dockerfile change:** the new version of the Stage 8 packaging test and full regression suite, fresh Docker Build, container startup/health, real HTTP inference inside Docker, Docker Compose E2E, load/peak-RAM profiling. Do **not** mark these Passed from the older 265-test run. Browser Swagger and other HTTP responses are supported by user terminal evidence on the prior commit.
- **Retest on Windows PowerShell:** `git pull --ff-only origin main`, `python -m pytest -q tests/test_stage8_delivery.py`, `python -m pytest -q`, `docker build --progress=plain -t mt5-persian-summary:stage8 .`, `docker image inspect mt5-persian-summary:stage8`, then `docker run` with the documented model volume and `-p 127.0.0.1:8002:8000` if host port 8000 belongs to another service. Verify `docker ps`, Docker health (HTTP liveness only), and `python tests/e2e_http_smoke.py --base-url http://127.0.0.1:8002 --large-upload`. Use `docker logs` for startup diagnostics; delete no model volumes unless explicitly intended. For Compose the declared host port remains 8000.
- **Acceptance:** Windows local service and all primary Stage 8 HTTP endpoints are confirmed functional, and regression passed before the Dockerfile-only hardening. The Docker image and container remain **unverified**. Stage 8 completion awaits successful image build/startup/real container HTTP inference and post-change regression results.

## Stage 8 Follow-up — PyTorch Wheel Integrity / Resume (2026-10-25)

- **Status: In Progress.** User pulled commit `e0fc7a073593d43536fe859a1b5347571c90f03f` with `git pull --ff-only origin main`; `git rev-parse HEAD` confirmed it. Repeated Stage 8 packaging checks `python -m pytest -q tests/test_stage8_delivery.py`: **5 passed, 1 third-party warning in 4.89s**. Repeated full Windows regression `python -m pytest -q`: **265 passed, 0 failed, 2 warnings in 11.96s**. These run on the **previous** Dockerfile, before the new pip-resume correction; no user Docker Model E2E has passed.
- **Second Docker Build failed:** `docker build --progress=plain -t mt5-persian-summary:stage8 .` successfully resolved the BuildKit syntax frontend, Python 3.12.10 base, and prior layers, but failed in the Docker dependency install step. PyTorch CPU wheel `torch-2.14.1+cpu-cp312-cp312-manylinux_2_28_x86_64.whl` was nominally 196.3 MB; logs show a dropped HTTPS connection and approximately `0.1/196.3 MB` transferred. `pip` rejected the data with SHA-256 mismatch (expected `5a6363570c753812540a05eb82380e329469cbe668643e88111414c12627711f`; received `b5a4b1d10c1c128d03166d5d229d7cd69d5be839ac366d718af2b6c3475749b0`); exit code 1. The mismatch is a security boundary: **do not disable or override wheel integrity checks**. The most likely cause is an incomplete/corrupted network response, but a genuine CDN/mirror inconsistency cannot be ruled out without independent byte-level verification.
- **Dependent commands did not validate Docker:** `docker image inspect mt5-persian-summary:stage8` returned no image; `docker run` failed because that Image was not built, regardless of registry authentication. No container existed for `docker ps`, `docker inspect` or `docker logs`. `curl.exe` to `127.0.0.1:8002` failed to connect, and the Docker-target HTTP smoke failed with `httpx.ConnectError` (`WinError 10061`); these are consequences of no listening container, not HTTP/service regression.
- **Targeted correction applied:** `Dockerfile` now upgrades pip inside Docker to `pip>=25.2,<27` before installing PyTorch; `pip` versions 25.2+ enable resumable wheel downloads by default. Both install commands request `--resume-retries 12`, plus the existing `--timeout 180 --retries 8`. BuildKit pip cache uses fresh `id=mt5-pip-v2` with `sharing=locked`, isolating potentially corrupt prior cache state. Official CPU-only PyTorch index, dependency compatibility check, Python image, security controls, one Uvicorn worker and model loading remain unchanged. A valid SHA-256 remains required. `tests/test_stage8_delivery.py` asserts the new flags and cache parameters. `README.md` records the failure and secure retry. **No new application dependency, runtime feature or secret.**
- **Local retest:** `git pull --ff-only origin main`; `python -m pytest -q tests/test_stage8_delivery.py`; `python -m pytest -q`; `docker build --progress=plain -t mt5-persian-summary:stage8 .`. Start Docker or Compose and run real model HTTP smoke only if Docker Build succeeds. Because host port 8000 was already in use in earlier logs, the `docker run` documented test may map `-p 127.0.0.1:8002:8000`, and E2E should target `http://127.0.0.1:8002`.
- **Not Run following this correction:** full pytest, Stage 8 focused pytest, Docker build, Docker container startup, Docker healthcheck, real Docker inference/E2E and Compose validation. Source on GitHub has been read back for static verification, but runtime acceptance remains unverified.
- **Remaining blocker:** reliable verified download of the official Linux CPU PyTorch wheel (or investigation of proxy/CDN if hash still mismatches). Stage 8 cannot be marked Completed before actual Docker inference and regression acceptance are recorded.

## Stage 8 Windows Third Verification — Docker CDN Incomplete Download (2026-10-25)

- **Stage 8 remains In Progress.** User reported explicitly that the local Uvicorn process had been stopped before retrying Docker, so host Uvicorn cannot be the cause of this Docker build failure. User pulled and verified GitHub HEAD `9c1aa8703877087852d4e0cc7fe1e3973218e8f4` (fast-forward). New focused test: `python -m pytest -q tests/test_stage8_delivery.py` **5 passed, 1 non-blocking warning** (4.37s); full Windows regression `python -m pytest -q` **265 passed, 0 failures, 2 deprecation warnings** (12.17s). These results are evidenced by the user's PowerShell output, not by assistant-side test execution.
- **Third Docker Build failed due to incomplete official CPU wheel download, not an app error:** the Dockerfile successfully upgraded pip 25.0.1 → 26.2.2 and invoked resumable downloads against the official PyTorch CPU index. During the ~196.3 MB Linux x86_64 PyTorch 2.14.1+cpu wheel retrieval, the underlying server repeatedly closed the connection; pip attempted 12 resumes, then failed after 13 attempts with only **796 kB / 196.3 MB** downloaded (approximately 0.41%). Error `incomplete-download`, exit code 1. HTTPS wheel checksum verification remained enabled. Upgrading pip/resume worked as intended; the external connection from Docker build environment remains unreliable. Do not increase retries indefinitely, turn off TLS/hash verification, or imply that local Windows' already installed PyTorch distribution can be reused in a Linux container.
- **Dependent Docker checks did not run meaningfully:** `docker image inspect mt5-persian-summary:stage8` reported no such image, and `docker run` cannot start an image that was not built. `docker ps` was empty; `docker inspect` found no container; host port 8002 refused connections; Docker HTTP E2E failed with `httpx.ConnectError: WinError 10061`. The absent process explains these dependent failures. No Docker model inference or Compose acceptance occurred.
- **Minimal documentation-only follow-up:** added a bounded 64 KiB byte-range probe for the exact PyTorch wheel, from both Windows `curl.exe` and the cached `python:3.12.10-slim-bookworm` container, in `README.md`. This distinguishes host-only vs Docker Desktop proxy/firewall connectivity issues without a costly image rebuild. Also document VPN/proxy routing and the fallback of a trusted remote Docker builder if local sustained transfer cannot be repaired. There are **no additional code, Dockerfile, test or dependency changes** in this response.
- **Next action:** run both bounded byte-range diagnostics and inspect Docker Desktop Settings → Resources → Proxies, VPN, Windows firewall and `com.docker.backend.exe` path as indicated by results. Rebuild the existing `Dockerfile` only after connectivity can sustain the full official Linux wheel. Once built, verify actual container startup, health, single real mT5 inference, TXT/PDF/DOCX E2E against port 8002, and Compose. Stage 8 status stays **In Progress** until Docker runtime acceptance is verified; do not state Completed.

## Stage 8 Host-and-Container CDN Range Probe (2026-10-25)

- **Stage 8 status: In Progress — external download connectivity blocker remains.** User executed the documented bounded range tests using the exact official Linux CPU PyTorch wheel URL, independently from Windows PowerShell and inside the unmodified official `python:3.12.10-slim-bookworm` Linux container, with local Uvicorn stopped.
- **Windows host result:** `curl.exe -L --range 0-65535 --max-time 30 ...` received HTTP **206 Partial Content** but only **58,923 of 65,536 bytes** after **30.006560 seconds**, returning `curl: (28) Operation timed out`. The host itself therefore has an unreliable or extremely slow connection to `download-r2.pytorch.org`; this is not merely an isolated Docker Desktop symptom.
- **Linux container result:** `docker run --rm python:3.12.10-slim-bookworm python -c ... urllib.request ... Range: bytes=0-65535` successfully fetched the base Python image from Docker Hub, then timed out during HTTPS response body reading (`TimeoutError: The read operation timed out`). The target CDN route is unusable in this environment even for a short range request. Successful Docker Hub pulls do not imply successful PyTorch CDN access.
- **Technical decision:** No application, Dockerfile or dependency versions changed; retries and resumable download have already been exercised. Do not disable TLS or wheel hash verification and do not retry lengthy Docker builds before the network is fixed. Next validation should use a separate working network, or inspect legitimate Windows/Docker VPN/proxy/firewall settings; repeat bounded range checks first. Alternatively a trusted off-host/GitHub Actions Docker build can produce a Linux image for later retrieval, subject to the separate registry/download requirements. Host Windows PyTorch wheels cannot be copied as Linux packages.
- **Verification:** host range probe **failed** (partial 206 then timeout); container range probe **failed** (read timeout); Docker base image download **passed**. A Docker image tagged `mt5-persian-summary:stage8`, container startup, Docker health, inference and Compose E2E remain **Not Run/Blocked**, not passed. The full Windows regression result remains **265 passed** from the prior user-provided run at HEAD `9c1aa8703877087852d4e0cc7fe1e3973218e8f4`. These observations were reported by the user; no assistant-side Docker test was executed. No commit SHA can be self-referenced in this progress entry; the last `main` commit identifies it.

## Stage 8 Follow-up — Empty CDN Responses and Manual Remote Build (2026-10-25)

- **Status: In Progress**, not Completed. Two subsequent Windows PowerShell `curl.exe -L --range 0-65535 --max-time 30` attempts to retrieve the official Linux CPU PyTorch wheel from `download-r2.pytorch.org` both failed at approximately 15.58 seconds with `curl: (52) Empty reply from server`, `HTTP 000`, **0 bytes downloaded**. Earlier host probes received partial data before timeouts and an independent Linux container probe also timed out. These outcomes support an unreliable external CDN/network path; they do not establish which upstream network component closed the connection, nor prove the user switched to a different network. Local Uvicorn state is unrelated.
- **No further pip retries or disabled verification:** Dockerfile and model dependencies intentionally unchanged. Increasing retries did not solve external transfer failure; the official wheel SHA-256 and HTTPS validation must remain enabled. Existing Windows unit/regression/HTTP and real-model tests are still evidenced by earlier user outputs (last measured full suite **265 passed** at commit `9c1aa8703877087852d4e0cc7fe1e3973218e8f4`); they do not show a successful Linux Docker build.
- **Added manual fallback:** `.github/workflows/docker-image.yml` with `workflow_dispatch` only, restricted to `main`, GitHub-hosted `ubuntu-24.04`, temporary `GITHUB_TOKEN` permissions `contents: read, packages: write`, pinned `actions/checkout` SHA, Linux image Build from unchanged repository Dockerfile, container HTTP liveness and OpenAPI route verification, and successful-build-only push to `ghcr.io/amirmahdimtz/mt5-persian-summary:stage8`. The workflow **does not execute automatically**, bundle model weights, or confirm inference. It must be manually started from GitHub Actions by a permitted user and can use GitHub Actions minutes/storage. Package visibility may require authenticated GHCR pull.
- **Documentation and test changes:** `README.md` documents Actions UI steps, GHCR image pull/tag, private registry authentication, packaging vs inference distinction, model download requirements and subsequent Docker E2E validation. `tests/test_stage8_delivery.py` adds a sixth fast structural assertion for workflow manual trigger, GitHub permissions, main branch, Build, liveness and publish commands. No added application dependency or runtime/inference change.
- **Checks performed:** workflow YAML was successfully parsed with `yaml.BaseLoader` in the assistant's isolated environment; static contract checks for trigger, permissions, steps, build/publish and HTTP smoke passed before GitHub upload. GitHub `main` content and final HEAD will be separately verified. **Not Run:** new workflow in GitHub Actions; registry publication or availability; GHCR pull on Windows; modified full pytest suite; actual Docker container and mT5 inference; Compose. No successful `docker build` or remote image is claimed.
- **Next acceptance action:** GitHub repository → Actions → `Stage 8 Docker remote build` → Run workflow → choose `main` and inspect job logs. On success, `docker pull ghcr.io/amirmahdimtz/mt5-persian-summary:stage8`, `docker tag` to local `mt5-persian-summary:stage8`; execute the prior documented `docker run` mapping host 8002 to container 8000; verify health and `python tests/e2e_http_smoke.py --base-url http://127.0.0.1:8002 --large-upload`. If the remote workflow itself fails PyTorch downloads or GHCR permissions, inspect its actual error rather than assuming success. Retest the newly added fast packaging test and full Python suite before Stage 8 is declared Completed.

## Stage 8 Windows Regression 266 and GHCR Pull Denied (2026-10-25)

- **Status: In Progress.** User ran `git pull --ff-only origin main` successfully, updating to GitHub HEAD `2b4b068ab64c1633a50cc2be315e875b53ee680c`. Windows Python 3.12 `python -m pytest -q tests/test_stage8_delivery.py`: **6 passed, 1 warning in 4.31s**. Windows full suite `python -m pytest -q`: **266 passed, 0 failed, 2 deprecation warnings in 15.32s**. No new application regression found from those test results.
- **GHCR availability not verified:** user immediately attempted `docker pull ghcr.io/amirmahdimtz/mt5-persian-summary:stage8`, which returned `error from registry: denied`. No GitHub Actions `Stage 8 Docker remote build` run status, build logs, successful `Publish validated image` job, package visibility or GHCR authentication was provided or independently confirmed. Therefore **do not infer** the image exists; `denied` may indicate an unpublished package or insufficient registry access. The workflow is `workflow_dispatch` only and **does not automatically run because it was committed, pulled or tested**.
- **Cascading failures:** `docker tag` and `docker image inspect` found no image; `docker run` failed because the tag was absent (a public-registry fallback error is not a Docker runtime bug); no container was running; HTTP at `127.0.0.1:8002` refused connections; Docker E2E failed with `httpx.ConnectError: WinError 10061`. All are consequences of not obtaining the image, not evidence that a functioning image or API failed.
- **Next acceptance step:** in GitHub Actions manually choose `Stage 8 Docker remote build` → `Run workflow` → `main`, and inspect the full job through `Publish validated image`. Only after its success, pull the exact tag from GHCR; if the package is private, authenticate with a token scoped for `read:packages` and required repository/package access. Do not put tokens in source or logs. If the workflow itself fails, diagnose the run logs; do not attempt `docker run` until `docker image inspect` finds a valid image. Then run actual Docker health and live model E2E to satisfy Stage 8 acceptance.
- **Verification evidence:** prior fast checks and full regression **Passed on user host** (266 total). Remote workflow run, actual GHCR publication, Docker image/startup/health, real inference and Compose remain **Not Run/Unverified**. No new Python packages or Dockerfile/source changes made for this update.

## Stage 8 GHCR Image Download Confirmed (2026-10-25)

- **Status: In Progress; runtime and real inference verification still pending.** User successfully executed `docker pull ghcr.io/amirmahdimtz/mt5-persian-summary:stage8` on Windows. Docker showed `Pull complete` for five image layers, returned `Status: Downloaded newer image`, and reported registry image digest `sha256:cd412cc060aab2c5d32d63445a1fbc09f84a3053fa8e7fcd61ce479d7daf6877`. This supersedes earlier `denied` observations for this user's latest pull: the GHCR tag is accessible and a Linux image was transferred successfully to the local Docker Engine. The user has not supplied GitHub Actions run logs, so the exact successful workflow run details, checks and source SHA embedded in the tag remain unverified by the assistant.
- **Still Not Run/Unverified:** local `docker image inspect` on the downloaded tag, tag normalization, container startup, Docker health endpoint and process logs, model checkpoint download/init and CPU inference in the container, TXT/PDF/DOCX HTTP E2E, memory/throughput profiling and Docker Compose runtime. Successful `docker pull` alone does not validate any of these. The previous full Windows regression evidence remains `266 passed, 0 failed, 2 warnings`.
- **Next acceptance commands:** `docker tag ghcr.io/amirmahdimtz/mt5-persian-summary:stage8 mt5-persian-summary:stage8`; `docker image inspect mt5-persian-summary:stage8`; `docker run -d --name mt5-persian-summary --init --memory 8g --cpus 2 --pids-limit 256 --security-opt no-new-privileges -p 127.0.0.1:8002:8000 -v mt5_hf_cache:/home/app/.cache/huggingface -e env_type=production mt5-persian-summary:stage8`; `docker ps --filter name=mt5-persian-summary`; `docker inspect --format '{{json .State.Health}}' mt5-persian-summary`; `curl.exe -i http://127.0.0.1:8002/api/v1/health`; `python tests/e2e_http_smoke.py --base-url http://127.0.0.1:8002 --large-upload`. First inference may require a separate Hugging Face checkpoint download to the named container volume. Complete Stage 8 only on independent successful Docker runtime/inference evidence.
- **Changes:** documentation-only acceptance progress update; Dockerfile, workflow, application source and dependencies remain unchanged. No new tests executed by the assistant.

## Stage 8 Final MVP Acceptance — Windows Docker Real E2E (2026-10-25)

- **Stage Number: 8 — Status: Completed (MVP acceptance scope).** The seven prior stages remain Completed. This final entry supersedes the historical Stage 8 `In Progress` reports above. The user-provided Windows Docker acceptance results satisfy the required Stage 8 plan: documented runnable service, three working summarization endpoints, real main-flow E2E checks including files/batch, clearly documented security and resource limits, and no identified placeholder among required MVP components. Running Compose, observing Docker's post-grace `healthy` flag, sustained load benchmarking and measuring graceful shutdown remain outside the narrow main-flow acceptance result and are explicitly listed below.
- **Changed files over Stage 8:** `Dockerfile`, `.dockerignore`, `compose.yaml`, `README.md`, `tests/e2e_http_smoke.py`, `tests/test_stage8_delivery.py`, `.github/workflows/docker-image.yml`, and `docs/IMPLEMENTATION_PROGRESS.md`. This final acceptance update changes only documentation (`README.md` and the present progress record). Existing FastAPI architecture, thin controllers, constructor injection, `src.*` imports, provider/model configuration and inference settings were unchanged. **Added Python dependencies: none**; Docker uses existing compatible ranges.
- **Technical decisions:** ship CPU-only Python 3.12.10 Linux image with one Uvicorn worker, non-root `app` user, loopback-bound host port, process-liveness Docker HEALTHCHECK, persistent Hugging Face model cache, resource and upload guard documentation, and opt-in real-model HTTP smoke. Earlier repeated failed local Docker builds were caused by an unreliable HTTPS path to the official 196.3 MB PyTorch Linux wheel, not app source; deliver the same Dockerfile's image through a manually triggered off-host GitHub Actions build and GHCR registry. The image does not bundle the checkpoint; real inference uses the existing lazily loaded model in the running container.
- **User-provided tests and results (Windows Python 3.12.10):** `python -m pip check` => no broken requirements; `python -m compileall -q src tests` => passed; `python -m pytest -q tests/test_stage8_delivery.py` => **6 passed, 1 nonblocking warning** in 4.31s; `python -m pytest -q` => **266 passed, 0 failed, 2 deprecation warnings** in 15.32s, after adding the workflow structural test. The local mT5 model, long-text and quality smoke scripts also executed successfully earlier in Stage 8; their output is not proof of factual correctness.
- **Docker image verification:** `docker pull ghcr.io/amirmahdimtz/mt5-persian-summary:stage8` successfully downloaded the package; `docker tag` completed; `docker image inspect mt5-persian-summary:stage8` succeeded and confirmed `linux/amd64`, `User=app`, `HF_HOME=/home/app/.cache/huggingface`, one Uvicorn worker, exposed port 8000, and the HTTP healthcheck. Image digest / image ID reported as `sha256:cd412cc060aab2c5d32d63445a1fbc09f84a3053fa8e7fcd61ce479d7daf6877`. A successful GHCR pull proves an image exists; the exact GitHub Actions build job log/run identifier and source SHA of the published tag were not separately provided.
- **Docker container verification:** `docker run -d --name mt5-persian-summary --init --memory 8g --cpus 2 --pids-limit 256 --security-opt no-new-privileges -p 127.0.0.1:8002:8000 -v mt5_hf_cache:/home/app/.cache/huggingface -e env_type=production mt5-persian-summary:stage8` returned container ID `8f97c0c94c2c74dd1e98ff539fff339596b3a9d37538127cc0c2cadc6c84fc94`. `docker ps` confirmed it `Up` with loopback-published host port 8002. Immediately after startup `docker inspect .State.Health` reported `starting` with no healthcheck logs, `docker logs --tail 100` was empty, and `curl.exe` returned `Empty reply from server`; this was before the service was demonstrated ready. The later HTTP E2E liveness check passed. **Final Docker HEALTHCHECK status was not observed**, so do not claim `healthy` from the initial `starting` result.
- **Real Docker HTTP E2E: PASSED (user-provided terminal transcript)** via `python tests/e2e_http_smoke.py --base-url http://127.0.0.1:8002 --large-upload`, which printed `PASS live HTTP E2E smoke; this is not a factual-quality benchmark`. Confirmed checks: GET health, Swagger/OpenAPI and all three POST operations; POST text with `short`, `medium`, `long`; single TXT, synthetic text-layer PDF and DOCX; multipart batch with all three generated files; malformed PDF sanitized HTTP 422; unsafe filename 400; invalid summary length 422; file above 20 MiB HTTP 413. `summary_chars=68` for multiple positive samples confirms generated output was accepted, not semantic-quality differentiation between tiers. No `httpx.ConnectError`, HTTP 503 or processing failure appeared in this completed run.
- **Failed tests:** none in the last Windows pytest regression or the successful Docker live HTTP E2E. **Transient observed anomaly:** an initial empty HTTP response at very early container startup while Docker HEALTHCHECK still reported `starting`; subsequent E2E passed. `^C` appears after the completed E2E output and is not evidence of a failed case or of the container stopping.
- **Not Run / known limitations / next-version backlog:** independent Docker `healthy` status after the start period; `docker compose up --build` runtime (the Compose file is structurally covered by the six Stage 8 tests); actual SIGTERM/graceful shutdown latency under running inference; cold-cache download and model load timing, peak Docker RAM, throughput/saturation/concurrent inference under load, memory OOM boundaries, large hostile document stress, production-grade external auth/rate limiting and real-world PDF RTL fidelity. The model's earlier sample omitted topics and misrepresented the direction of pollution change; repetitive long-document summaries can be overly short. Upload guards are not a full malicious-PDF sandbox. No OCR, database, UI, durable queue, GPU or model quality guarantee. These are documented residual operational/quality issues, **not claims of tests Passed**.
- **Acceptance conclusion:** stage 8 scoped plan criteria met based on locally exercised Docker and actual real-inference HTTP tests; **MVP delivered, Stage 8 Completed**. Preserve the versioned image tag and documented GHCR/persistent cache procedure. Follow-up optional checks can include `docker inspect --format '{{json .State.Health}}' mt5-persian-summary`, `docker logs --tail 100 mt5-persian-summary`, and controlled `docker stop mt5-persian-summary` after all requests are finished; tests require user execution and cannot be reported passed until observed. No further MVP implementation stage is scheduled. Any next scope should be explicitly requested.
- **Commit message for final documentation:** `docs: finalize Stage 8 MVP Docker E2E acceptance`. The final commit SHA cannot appear inside its own content; see the verified GitHub `main` HEAD after this documentation update.


## Stage 8 Final Post-Acceptance Health Verification (2026-10-25)

- **Stage 8 remains Completed.** Following the verified final acceptance documentation commit `99c72c2b8436d03cd62ecf1ddc4b6e1a06ae17f7`, the user ran `git pull --ff-only origin main` (fast-forward), and `git rev-parse HEAD` matched that exact SHA. Only `README.md` and `docs/IMPLEMENTATION_PROGRESS.md` changed in the pull; no application implementation or container runtime source changed.
- **Passed (user-provided Windows PowerShell results):** `python -m pip check` => `No broken requirements found.`; `python -m pytest -q` => **266 passed, 0 failed, 2 deprecation warnings in 12.28 seconds**. The known warnings are Starlette TestClient/`httpx` deprecation and `httpx` deprecated raw `data` upload usage; no new failing tests.
- **Docker sustained liveness now verified:** `docker ps --filter name=mt5-persian-summary` showed container `8f97c0c94c2c`, image `mt5-persian-summary:stage8`, **Up 51 minutes (healthy)**, with host-only port `127.0.0.1:8002->8000/tcp`. `docker inspect --format '{{json .State.Health}}' mt5-persian-summary` returned **`Status=healthy`, `FailingStreak=0`**, with five visible recent healthcheck records all having `ExitCode=0`. `curl.exe -i http://127.0.0.1:8002/api/v1/health` independently returned **HTTP 200** with `{"status":"ok"}`. This supersedes the pending final-`healthy` verification limitation documented in the immediately preceding acceptance entry.
- **Server logs:** repeated `GET /api/v1/health` returned HTTP 200; `POST /api/v1/summarization/text`, `/file`, `/files` were all recorded with HTTP 200 during the earlier E2E run. The observed HTTP 400 (unsafe filename), 413 (oversized upload), and 422 (invalid PDF and invalid summary length) reflect intended E2E negative tests, not unexpected production faults. The earlier empty HTTP reply occurred during initial health `starting` state; subsequent successful healthy checks and real E2E indicate no persistent liveness failure.
- **Verification and residual scope:** actual Docker HEALTHCHECK status **Passed** after sustained operation; real container HTTP E2E and Python regression **Passed** in user-provided transcripts. **Still Not Run:** Docker Compose runtime, controlled SIGTERM/graceful stop under inference, sustained-load throughput, peak memory, cold-cache latency, and factual-quality benchmark. These operational/quality follow-ups are not part of the already accepted Stage 8 MVP gate and must not be described as Passed.
- **Files changed for this verification:** only this progress log. **Dependencies added:** none. **Known issues and next step:** previously documented factual faithfulness limits and unsupported features still apply; the delivered MVP requires no new stage. The commit corresponding to this progress update is identified by the final verified GitHub `main` SHA because a commit cannot embed its own final SHA.


## Post-MVP Documentation — Accessible Persian README (2026-10-25)

- **Stage status remains: Completed (all eight MVP stages).** User requested an approachable README, to be committed directly to `main`, for anyone wanting to run and test the existing mT5 summarization REST API. This is a documentation-only post-delivery improvement, not a new feature stage.
- **Changed files:** `README.md` was rewritten in Persian with an immediate model/service description, a Docker GHCR pull-and-run quick start on loopback port 8002, Docker health and Swagger opening commands, practical step-by-step instructions for text/file/files, `short/medium/long` semantics, PowerShell and Bash HTTP examples, local Windows/Linux/macOS source installation, model ID/pinned revision and license qualification, architecture/data-flow outline, actual upload/resource budgets, expected HTTP error codes, restart/cache troubleshooting, security warnings, and links to verification/architecture documents. The previous long technical English README was reduced from **29,489** to **16,086** characters while prioritizing first-use instructions. Existing implementation, Dockerfile, model revision, workflow, and dependencies were not modified.
- **Important newly documented real-world result:** user submitted a real Docker `/api/v1/summarization/file` run for `persian_summarization_test_8_pages.pdf` (18,052 extracted characters). Both `medium` and `long` produced the exact same 113-character summary despite HTTP 200 and `success=true`. This highlights that summary length is a generation cap, not a target or guarantee; on long PDFs, semantic coverage and sentence completeness can be inadequate. This is now called out in the README along with earlier factual-inconsistency observations; no model behavior was changed or falsely claimed to be fixed.
- **Verification (assistant-side):** fetched actual `README.md` and `src/application/summarization/` Controller/DTO, YAML model settings, Stage 2 model verification record, Stage 8 tests and E2E script from GitHub; independently confirmed referenced architecture, plan, progress and model verification files exist on `main`. Static README checks passed for balanced Markdown code fences (**32 fence markers / 16 pairs**), expected GHCR pull command, Swagger URL/PowerShell launcher, all three API paths, exact pinned Hugging Face revision, links to real documentation and the new measured quality caveat. Fetched the rewritten README back from GitHub and confirmed it is **16,086 characters**.
- **Tests:** **Not Run** for this docs-only change: user-side `python -m pytest -q`, new Docker run and live mT5 inference. Prior user evidence remains **266 passed, 2 nonblocking deprecation warnings**, plus successful live Docker HTTP E2E and sustained `healthy` checks before this README update. No new dependencies or source tests added.
- **Known issues:** quality of short summaries of long documents, unchanged model generation ceilings and factual fidelity, unsupported OCR/authentication, peak RAM and Compose runtime unverified. README is a user guide, not proof of model accuracy or Production readiness. **Next step:** contributors/users should follow the new README on a local machine and verify generated summaries against source texts before real-world use.
- **Commits:** README rewrite `418ba462d2dfe73e2ee705ac5633df3030a9dbbb` (`docs: rewrite README as practical Persian model and API guide`). This progress-only follow-up commit SHA is verified by inspecting the GitHub `main` head after the write.


## Post-MVP Documentation — English README Localization (2026-10-25)

- **Status: Completed; all eight original MVP stages remain Completed.** User requested that the new accessible README be in English rather than Persian. This was a documentation localization task; no feature, dependency, model ID, Dockerfile, runtime configuration, or API contract changed.
- **Changed file:** `README.md` was rewritten in English while retaining the beginner-friendly quick-start structure and exact commands for the prebuilt GHCR image, Docker loopback port 8002, Swagger text/file/files walkthrough, optional direct REST API examples for PowerShell and Linux/macOS, YAML settings, local Python setup, upload limits, errors, test instructions, architecture and verified Stage 8 outcomes. Persian strings only remain in JSON/API command examples as authentic model inputs; no Persian explanatory headings remain.
- **Quality transparency retained:** model output is not guaranteed factually faithful; the documented eight-page PDF with 18,052 extracted characters returned the same 113-character summary for `medium` and `long`. The distinction between HTTP success, model readiness and semantic quality was preserved.
- **Verification:** the updated English `README.md` was fetched back from GitHub `main` and inspected. Static checks verified balanced 16 Markdown code-block pairs, English headings, expected API routes, exact pinned model revision, GHCR pull and PowerShell Swagger-launch commands, the real summary-quality caveat, and existing relative documentation links. **Not Run:** Python regression, Docker runtime, Compose, new model inference or E2E; this change is only Markdown content. Most recent reported runtime evidence remains 266 passed and actual healthy Docker E2E before the README-only update.
- **GitHub commit:** `b345b9b9bcc5769df6e7175676eb28dc0b2cb926` (`docs: provide full English README and user guide`), on `main`. This supplemental Progress commit is verified separately against the GitHub branch head after updating. **Next step:** users may pull `main` and follow the English README; model-quality improvement is a separate future implementation task, not completed here.


## Stage 9 — Quality Benchmark & Root-Cause Analysis (2026-11-01)

- **Stage Number / Status:** 9 — **In Progress**. All eight original MVP stages remain Completed. Stages 10–13 are Not Started. Real mT5 baseline and authoritative human labels are missing; Stage 9 Acceptance Criteria are **not yet met**.
- **Baseline GitHub HEAD:** `b5f1df5288f93e9a160948cfd8eb3b304daebea9` on `main`; repository write permission verified before changes. New development plan `docs/POST_MVP_DEVELOPMENT_PLAN.md` reviewed with architecture and existing model/chunking/services/tests.
- **Changed files:** `benchmarks/quality_benchmark.py` (versioned dataset validation, optional real-model runs, SHA-bound human review template and scoring, extraction anchor diagnostics), `benchmarks/fixtures/quality_v1.json` (seven original synthetic Persian cases, five dev/two holdout), `tests/test_quality_benchmark.py` (22 isolated tests), `docs/STAGE9_QUALITY_BASELINE.md` (methodology, root-cause hypotheses, review criteria, commands), `.gitignore` (protect local raw outputs), and this `docs/IMPLEMENTATION_PROGRESS.md` entry. **Production Runtime/Endpoints: untouched.**
- **Technical decisions:** use standard-library JSON and SHA-256, no new runtime dependency; no model replacement or generation changes. All seeded facts carry literal `source_quote` evidence. A reviewer must mark each fact `covered`, `omitted`, or `distorted` and each atomic output claim `supported`/`unsupported`; evidence quotes are substring-checked but human semantic validation remains mandatory. Scoring rejects mismatched datasets/run hashes or incomplete individual reviews; partial reviews are explicitly counted and cannot be accepted as a full baseline. Raw results are written using exclusive create (`x`) to prevent accidental overwrite. `inspect-extraction` is separate from inference to distinguish PDF RTL problems from model behavior.
- **Added Dependencies:** none. Python 3.12 and existing `requirements.txt` retained.
- **Tests (isolated authoring workspace):** `python -m pytest -q tests/test_quality_benchmark.py` **23 passed, 0 failed**; `python -m compileall -q benchmarks tests` **passed**; `python -m benchmarks.quality_benchmark validate` **passed** (seven cases; dev=5, holdout=2). These tests use mock model wiring and do **not** assert factual quality of actual mT5. The complete repository was not available in the execution sandbox due blocked GitHub DNS, so its older 266-case suite could not be rerun. Real mT5 inference, reviews, PDF source comparisons, Docker and benchmark on representative documents **Not Run**.
- **Known Issues / blockers:** only seven synthetic seed cases; the proposed 30–50 licensed representative documents and 100 future Q&A labels have not been collected. Actual eight-page user PDF (18,052 extracted chars) is not available in this workspace. No measured `Fact Coverage`, `Unsupported Claim Rate`, `Latency` or `Peak RAM`; qualitative prior failure anecdotes are not newly reproduced measurements. Numerical acceptance thresholds and held-out benchmark policy need a real baseline and reviewer sign-off before Stage 10 tuning.
- **GitHub source commits (verified by direct connector responses):** benchmark runner `9c84053dd515b8128c19e1df96fe8ac086da94e0`; dataset `de17aa7a3b21f283be9d73445d79510458fa1eb4`; tests `832fd5001aee9bb16e9798540a5ce2db726c0f57`; quality documentation `e3e08a871b6bd9c7e8a8064831e6235ab9ed5284`; ignore rules `84b97ab877674bdc3352c2c78bde834d3fb76cbc`. This Progress documentation commit is not self-referential; verify current GitHub `main` SHA after it is created.
- **Local verification:** `git pull --ff-only origin main`, activate existing `.venv`, `python -m benchmarks.quality_benchmark validate`, `python -m pytest -q tests/test_quality_benchmark.py`, `python -m pytest -q`, and `python -m benchmarks.quality_benchmark run --split dev --output local_quality_dev_run1.json`. After manually reviewing output, run `review-template` and `score` as documented in `docs/STAGE9_QUALITY_BASELINE.md`.
- **Stage 9 targeted follow-up:** strengthened input validation to reject non-string fact types and limited saved model settings to an explicit nonsecret allowlist. Added a regression test proving unrecognized secret-like config keys are not serialized. Local isolated benchmark suite rerun: **23 passed, 0 failed**. Source and test fix commits: `182790bddda8cbc964ae14f70868ace61bd77821`, `299ea63af1ce8228e4b04b251e4e3eb2eb610dda`; benchmark documentation count correction: `d082b1449254107daa54df2d6c2fe7600602a491`. No real model test was run.
- **Next Stage Readiness:** **Blocked until Stage 9 real model baseline, human review, representativeness assessment and numerical stop/go thresholds are recorded**. Do not start Stage 10 quality tuning or assert Stage 9 Completed based on the isolated mock tests alone.


### Stage 9 user-side reproducibility update (2026-11-01)

- **Status:** Stage 9 remains **In Progress**. The previously unrun real-model `dev` seed baseline has now been executed by the user, but representative data, independent semantic review, PDF extraction diagnosis, and stop/go thresholds remain pending.
- **Tests verified from user logs:** `python -m pytest -q tests/test_quality_benchmark.py` — **23 passed in 3.42s**; `python -m pytest -q` — **289 passed, 2 deprecation warnings in 15.42s**; `python -m benchmarks.quality_benchmark validate` — **7 cases (5 dev, 2 holdout)**, dataset SHA-256 `cc907d6b16a4b68685b280002bb0a0f550ce6ce3966941c8732702c016f8a9a9`. Environment dependencies checked: no broken requirements.
- **Real-model dev runs:** user-submitted `local_quality_dev_run1.json` contains **15 successful calls** (5 cases × 3 tiers), model `nafisehNik/mt5-persian-summary` at pinned revision, CPU. **5/5 cases** generated identical text across all three tiers. First call 114.048s, all recorded call times sum 253.064s (inclusive of model warm-up). Output 19–33 encoded tokens including specials; not a peak-memory or latency benchmark.
- **Observed quality defects:** the pollution-decrease and software-support-cost-increase facts were both reversed; meeting owner/deadline/next meeting/budget facts were omitted. A provisional, assistant-generated review suggests **fact coverage 3/19 = 15.8%, distortion 2/19 = 10.5%, omission 14/19 = 73.7% per tier; unsupported-claim estimate 3/8 = 37.5% per tier**. These are **draft annotations, not human-accepted or statistically representative results**. Evidence, assumptions and limitations are detailed in `docs/STAGE9_QUALITY_BASELINE.md`.
- **No runtime/source-code changes** for this update; progress and baseline documentation only. New benchmark documentation commit: `a9a5924331a1aac7c858789af3d9f962dd9c9b17`. Actual run/review artifacts remain local and must not be committed.
- **Not Run / Missing:** independent complete review, `holdout` model run, peak RAM, extraction check on actual PDF, representative licensed document set and final acceptance thresholds. **Next Stage Readiness:** not yet met; Stage 10 tuning must not be claimed as commenced.


### Stage 9 audit and real-source evaluation scaffold (2026-11-01)

- **Stage:** 9. **Status: In Progress.** User explicitly requested factual review of five unique outputs, addition of accessible real documents and proposed Stage 10 gates. No Stage 10 runtime change was authorized or implemented.
- **Changed:** `benchmarks/quality_benchmark.py` (accept a distinctly marked `PROJECT-REFERENCE-ONLY` evaluation dataset alongside original CC0 fixtures; reject malformed licenses); added `benchmarks/project_document_dataset.py`, `benchmarks/fixtures/real_project_documents_v1.json`, `tests/test_project_document_dataset.py`, `docs/STAGE9_SEED_AUDIT_AND_GATES.md`; updated `docs/STAGE9_QUALITY_BASELINE.md` and this Progress file.
- **Five-case semantic audit:** used the previously submitted real CPU results and prior assistant-proposed fact/claim labels. Verified **3 covered / 14 omitted / 2 distorted unique facts** (19 total) and **3 unsupported / 8 atomic claims**, with a judgment-sensitive warning verb; **all 5 cases identical across three requested lengths**. Two unambiguous meaning inversions remain. This is **assistant review, not independent human sign-off**.
- **Real-source catalog:** three actual, pinned GitHub project documents: `Service_Architecture_Guide_FA.md`, `IMPLEMENTATION_PLAN.md` (dev), `docs/POST_MVP_DEVELOPMENT_PLAN.md` (holdout). The manifest references existing Markdown and expected facts without embedding or re-licensing its bytes. Prepare with `python -m benchmarks.project_document_dataset --output local_quality_project_v1.json`; run with `python -m benchmarks.quality_benchmark --dataset local_quality_project_v1.json run --split dev --lengths medium --output local_quality_project_dev_run1.json`. The existing /local_quality_* ignore policy keeps raw outputs local.
- **Technical decisions:** all source paths must remain inside the cloned repository; exact Git blob hashes and evidence quotes are checked. On source drift, fail rather than silently changing benchmark data. Holdout is reserved. This is a real-document **reference and evaluation scaffold**, NOT completed real-model inference and NOT PDF/DOCX validation.
- **Added dependencies:** none.
- **Tests:** isolated authoring workspace: `python -m pytest -q tests/test_quality_benchmark.py tests/test_project_document_dataset.py` **32 passed**, compileall passed; actual user-side environment had previously run **289 passed, 2 warnings** before these new edits (not rerun against the current GitHub head). Two real source blobs and quotes were checked locally; third source blob/quotes checked against live GitHub but complete three-case materialization was **Not Run** in local sandbox because GitHub raw download was inaccessible. User-side Stage 9 real-document inference **Not Run**.
- **Provisional Stage 10 quantitative gates:** on unique seeded dev cases with identical tiers counted once: `Fact Coverage >= 8/19`, zero critical pollution/cost direction inversions and no new fact distortions, unsupported claim rate `<= 12.5%` subject to reviewer-agreed claim segmentation, meaningful distinct short/long on at least 3/5 cases; see `docs/STAGE9_SEED_AUDIT_AND_GATES.md`. These gates are **not yet production acceptance** without representative corpus and independent semantic sign-off.
- **Known blockers:** no permitted actual meeting minutes, external multipage selectable-text PDF or DOCX supplied; the three source docs are **Markdown** and do not validate file extraction. No independent human review of AI-drafted labels; no completed real-model run on new sources; peak RAM/warm latency not characterized; holdout unrun; representative numeric thresholds not finalized.
- **GitHub source commits:** `79ad911884070ab28ba6a762ffea30324cfaad28` (benchmark format guard), `5d001d6861fa08ea897c02632b990133e836e73f` (source materializer), `e1b1667340640abe9aed13114d74ed107e602d39` (three-source catalog), `a1264e261b3149db93d3b9ac63ac0e9d38b53418` (new tests), `3b368f5db2891eff889d0d02256a7577db722e82` (audit/gates), `9faa0e6ae0388f209c4d082d31b5a433a7866cad` (baseline link). This entry is not self-referential; check GitHub `main` after commit.
- **Next Stage Readiness:** **Not yet ready to declare Stage 9 Completed**. Run new real-document dev baseline on user CPU, review its claims, obtain representative authentic minutes/PDF/DOCX and human approve gates, then update Progress. The main service remains unchanged.


### Stage 9 Windows cross-platform benchmark correction (2026-11-01)

- **Stage / Status:** 9 — **In Progress**, not completed. Reported by user after pulling `7c0c2918a2a9a26f5dead14edf774488790b2f32` on Windows PowerShell.
- **Observed failures (before fix):** targeted suite **31 passed, 1 failed**, full suite **297 passed, 1 failed, 2 nonblocking warnings**; failing `test_project_dataset_validates_without_relicensing` compared raw UTF-8 decoded text with `Path.read_text()` (LF-translating) and thus disagreed on `CRLF` versus `LF`. The real-project dataset materialization also failed on first Markdown source due to Windows checkout `CRLF` differing from the pinned `LF` Git blob. Subsequent `FileNotFoundError` when validating/reviewing is a downstream consequence of no dataset output being created.
- **Changed Files:** `benchmarks/project_document_dataset.py` (strict SHA match on original bytes, then retry only CRLF→LF canonicalization against the **same** approved blob; preserve drift detection), `tests/test_project_document_dataset.py` (raw-decoded comparison, CRLF acceptance and modified-content rejection tests), `docs/STAGE9_SEED_AUDIT_AND_GATES.md` (troubleshooting/verification), and this Progress record. Runtime service/config and manifest pinned hashes are **unchanged**. **Dependencies:** none added.
- **Local tests in assistant's isolated authoring environment:** `python -m pytest -q tests/test_quality_benchmark.py tests/test_project_document_dataset.py` **34 passed**; `python -m compileall -q benchmarks tests` **passed**. Real Git-tracked architecture/plan documents were tested with deliberately converted `CRLF` copies and original pinned Git SHA/fact quotes: **passed**. Full GitHub checkout regression test, all three pinned real-document materializations, actual mT5 inference, Docker and the user's Windows test rerun **Not Run** in this environment.
- **GitHub commits:** `dc968050a83b8841b706b380a90e08816ad8682d` (code), `ff36687e463cf2acb37e6f08968f7619c0f2c02e` (tests), `5b11f62d84330ae4dbcfc673021c8d345aef8099` (troubleshooting docs). Verify current `main` head after this progress update; this entry does not include its own SHA.
- **Next Stage Readiness:** Stage 9 remains pending complete real-model document evaluations, independent fact-annotation review, representative selectable-text PDF/minutes and signed-off Stage 10 acceptance thresholds. First rerun Windows 34 target tests and full suite, then `project_document_dataset` and `quality_benchmark validate`, and only then run real model on new dev cases.


### Stage 9 authentic-project Markdown inference results (2026-11-01)

- **Stage:** 9, **Status: In Progress**. The user pulled the CRLF fix and reran Windows tests: targeted Stage 9 tests **34 passed** (2.92s), full regression **300 passed, 2 deprecation warnings** (10.51s).
- **Actual data:** `python -m benchmarks.project_document_dataset --output local_quality_project_v1.json` succeeded for **3 pinned authentic project Markdown docs** (2 dev, 1 holdout). `quality_benchmark --dataset local_quality_project_v1.json validate` reported SHA-256 `fbc292ba36d07581614810efad42f0585ca9a50605e70a966048c33b9ac63e3c`. CRLF migration fix is verified by the user's run.
- **Inference result (from user-uploaded JSON, real pinned CPU mT5):** `quality_benchmark --dataset local_quality_project_v1.json run --split dev --lengths medium --output local_quality_project_dev_run1.json` produced 2 successful output records: `real_architecture_guide` 75.247s / 46 encoded tokens including specials, repetitive generic ChatGPT wording; `real_mvp_plan` 50.958s / 23 tokens, generic mT5 summary. **No holdout inference**, 126.205s total recorded inference benchmark timing; peak RAM not measured.
- **Assistant semantic audit against source quotes:** **0/6 covered, 6/6 omitted, 0/6 distorted expected facts**, with the two very broad claims judged source-supported, i.e. **0/2 unsupported draft claims**; repetition and missing detail remain severe. **These labels are assistant-proposed, not independently human signed off**. Full evidence and exact outputs recorded in `docs/STAGE9_QUALITY_BASELINE.md`.
- **Changed Files:** Documentation only (`docs/STAGE9_QUALITY_BASELINE.md`, `docs/IMPLEMENTATION_PROGRESS.md`). **Technical Decision:** no inference/model/pipeline changes in Stage 9; retain human review and representative PDF/minutes evaluation as prerequisites. **Dependencies:** none. **Tests:** user-run full 300 passed and 34 targeted passed; assistant did not rerun entire repo after these docs-only changes.
- **Source documentation commit:** `35df15435b52797e27e9ddfc6b50938be0914b32` (`docs: capture real project model outputs and coverage audit`). This entry does not embed its own new commit SHA; verify current `main` after commit.
- **Known gaps:** actual multipage selectable-text PDF and original meeting minutes unavailable; extraction not tested; no independent human review; no representative 30–50-document baseline or peak RAM; Stage 10 gates remain provisional. **Next Stage Readiness:** not ready to declare Stage 9 completed.


### Stage 9 user-scored authentic project metrics (2026-11-01)

- **Stage / Status:** Stage 9 — **In Progress**. User executed `quality_benchmark score` successfully for the two authentic project `dev` Markdown documents, using an assistant-drafted review file, yielding `reviewed=2 unreviewed=0`. The user provided the complete `local_quality_project_dev_metrics_checked.json` contents.
- **User-computed metrics:** dataset SHA-256 `fbc292ba36d07581614810efad42f0585ca9a50605e70a966048c33b9ac63e3c`, `runs=2`, `successful_runs=2`, `reviewed_runs=2`, `fact_counts={covered:0, distorted:0, omitted:6}`, `fact_coverage=0.0`, `fact_distortion_rate=0.0`, `claims_reviewed=2`, `unsupported_claim_rate=0.0`. Fact omission: action=3, number=1, topic=2. Only **medium** was run; average **91.5 characters**; the empty `identical_output_across_tiers` list cannot establish length control without short/long outputs.
- **Interpretation:** scoring confirms review completeness and arithmetic, **not independent semantic correctness**. Two broad source-supported claims coexist with **zero retention of the six specific required facts**; the architecture response also repeats an unhelpful generic phrase. The human-review requirement remains unmet.
- **Changed Files:** this progress document only. **Added Dependencies:** none. **Tests:** no new automated tests or model inference; most recent user-reported full suite: 300 passed, 2 warnings, targeted: 34 passed. **Known Issues / Next Stage Readiness:** no approved independent review, representative third-party documents, source PDF/minutes extraction evaluation, peak RAM or final signed-off Stage 10 gates. Stage 9 remains In Progress; Stage 10 not started.


### Stage 9 engineering baseline closeout (2026-11-01)

- **Stage / Status:** **Stage 9 — Completed as the reproducible engineering benchmark and root-cause triage deliverable.** This is a deliberately bounded engineering completion, **not certification of mT5 factual quality**. Stage 10, 11, 12, 13 remain Not Started.
- **Formal acceptance checks:** (1) CC0 fixed seven-scenario benchmark, distinct pinned real-source evaluation set and source-evidence labels are reproducible; (2) actual CPU mT5 reproduced short, multitopic and repeated-long failure categories; (3) original plaintext/Markdown model-input observations are demonstrably independent of PDF/DOCX extraction while the unavailable original PDF remains untested; (4) a numerical Stage 10 seed regression protocol and proposed Stage 11/13 future gates have been frozen **before** optimization. Detailed evidence and caveats: `docs/STAGE9_BASELINE_SIGNOFF.md`.
- **Model seed baseline:** user's five unique synthetic dev cases and three tiers: 15 successful outputs, 3/19 essential facts covered, 2/19 distorted, 14/19 omitted per unique tier; 3/8 assistant-drafted unsupported claims (weather warning label disputed); identical output text in all three length tiers for all five cases.
- **Real project-source baseline:** user's two authentic repository Markdown dev documents (`medium` only) yielded 2 successful model outputs, 0/6 task-specific facts covered, 6/6 omitted, 0/2 broad claims unsupported under draft labelling. Measured repeated-four-gram fraction was **40%** on the architecture summary, **0%** on the plan summary, **20%** across the two; reported tokens averaged 34.5 including specials vs the 80-token medium cap. These are observations, **not independently human-validated accuracy claims**.
- **Changed Files:** `benchmarks/quality_benchmark.py` (deterministic repeated-four-gram diagnostic, output budget, token count and cap diagnostics); `tests/test_quality_benchmark.py` (3 extra tests); `docs/STAGE9_BASELINE_SIGNOFF.md` (new formal source/protocol/triage report); `docs/POST_MVP_DEVELOPMENT_PLAN.md`, `docs/STAGE9_QUALITY_BASELINE.md`, this file (current status/protocol). **Architecture:** benchmark changes isolated from HTTP/ASGI and ML provider. **Added Dependencies:** none.
- **Verification (assistant isolated environment):** `python -m pytest -q tests/test_quality_benchmark.py tests/test_project_document_dataset.py` **37 passed**; `python -m compileall -q benchmarks tests` **passed**; rescored user's real project dev outputs with the actual review fields: **0/6 coverage; 1/2 repeats; 0/2 exceed the medium cap**. The most recent **user-side full regression before these new changes** was **300 passed, 2 nonblocking warnings**. Full repository suite and Windows tests **not rerun after the three new tests**: report this as Not Run, not Passed.
- **Frozen development gates for Stage 10:** unique synthetic fact coverage ≥8/19, zero critical direction reversals, no fact distortion, unsupported claim rate ≤12.5% under fixed claim segmentation, short/long distinct on ≥3/5 cases, authentic project documents ≥3/6 covered, architecture phrase repetition zero, and no API regression. They are **development regression gates**, not release thresholds. See `docs/STAGE9_BASELINE_SIGNOFF.md`.
- **Known limitations / deferred release evidence:** no third-party approved multipage text PDF or real minutes, no original anecdotal eight-page PDF, no independently signed human labels, no representative 30–50-document/100-question set, no peak memory or warm-only CPU latency, no per-hierarchy-level tracing. Those are **recorded Stage 10/11 investigation and Stage 13 validation risks**; do not claim them met. Holdouts remain untouched; no tuning/model weights have changed.
- **Next Stage Readiness:** **Stage 10 may begin on the frozen development benchmark with these caveats**. Production model-quality acceptance remains blocked until representative documents, independent review and held-out evaluation. This progress entry is not self-referential with a commit SHA; verify `main` head after commit.


### Stage 10 implementation started — candidate v1 (2026-11-01)

- **Stage:** 10. **Status: In Progress**, not completed; Stage 9 remains Completed as a diagnostic baseline. User explicitly requested starting Stage 10 coding on `main`; production quality acceptance has **not** been verified.
- **Changed files:** `src/infrastructure/ml/mt5_model_provider.py` (typed and bounded `no_repeat_ngram_size` with 0 as original default; pass to `generate`), `src/core/services/summarization/text_chunking_service.py` (prefer full Markdown heading starts near safe chunk boundaries; exact normalized text coverage and tokenizer checks retained), `src/host/res/appsettings.development.yaml` (candidate ngram=3), `src/host/res/appsettings.yaml` (production decoding baseline=0), `benchmarks/quality_benchmark.py` (capture generation knob), `benchmarks/stage10_compare.py` (new paired raw run CLI), `tests/test_mt5_model_provider.py`, `tests/test_text_chunking_service.py`, `tests/test_stage10_compare.py`, `.gitignore`, `docs/STAGE10_EXPERIMENT_V1.md`, and this Progress document.
- **Technical decisions:** Production decoder remains at Stage 9 behavior; Development runs an **opt-in environment-specific trial** with no-repeat 3, without changing model weights, revision, API, DI or inference limits. Markdown heading grouping is a shared lossless structural improvement but can change production outputs for headed text. The comparator rejects mismatched dataset SHA or unpaired keys, does not leak summaries or arbitrary model metadata and **never infers semantic improvement** from length/repetition. All local `local_stage10_*.json` experiment files are ignored by Git.
- **Added dependencies:** none.
- **Tests performed in assistant isolated sandbox:** source-equivalent `benchmarks.stage10_compare` and its isolated new tests plus available baseline Stage 9 benchmark suite: **38 passed**, `python -m compileall -q benchmarks tests` **passed**. An isolated exact new section-heading regex smoke test **passed**. A comparator smoke run on 15 identical records **passed**, reporting 15 paired/unchanged and `NOT_EVALUATED`; its locally staged fixture SHA differed from user's GitHub fixture, so this smoke used a **temporary test-only re-hashed copy** and is not a user dataset result.
- **Tests Not Run:** User-side Windows targeted and complete regression **not yet rerun on Stage 10 head**; actual Stage 10 mT5 CPU candidate inference, fact annotation, PDF/DOCX extraction, peak RAM, comparison against the Stage 9 approved regression gates and reserved holdout **not run**. Previous user verification **before Stage 10 changes** was 303 passed, 2 warnings, targeted Stage 9 37 passed.
- **Baseline / acceptance:** immutable source `docs/STAGE9_BASELINE_SIGNOFF.md`. Stated gates: synthetic covered ≥8/19, zero direction inversions and new fact distortions, unsupported claims ≤12.5% under review, ≥3/5 distinguishable short/long, authentic-project ≥3/6 facts retained, zero architecture-summary repeated four-grams, no API regression. Until actual CPU output and human review, all new candidate semantic gates remain `NOT_EVALUATED`.
- **Known issues / risk:** n-gram constraint might shorten valid text or suppress necessary repeats; Markdown headings are not guaranteed to appear in extracted PDF/DOCX; map/reduce source-fact loss remains unisolated; benchmark sample size and human review are insufficient for production sign-off. Stage 11–13 not started.
- **Next Stage Readiness:** continue Stage 10 iteration only after the user runs `docs/STAGE10_EXPERIMENT_V1.md` PowerShell commands and supplies paired candidate runs; do not declare Stage 10 Completed without independent semantic evaluation and actual improvement. Source commits are linked from GitHub history; confirm branch head after this Progress update.


### Stage 10 Windows v1 benchmark and Stage 8 profile-contract correction (2026-11-01)

- **Stage / Status:** 10 **In Progress**, not Completed. Last completed stage 9.
- **Observed user-side checks (against candidate v1 before this correction):** `pip check` no broken requirements; `compileall` succeeded; `pytest -q` **318 passed, 1 failed, 2 warnings**. Only failing test: `tests/test_stage8_delivery.py::test_model_settings_are_unchanged_between_profiles` (legacy equality expectation versus intentional development-only `no_repeat_ngram_size: 3` / production `0`).
- **Root cause and fix:** Stage 8 test assumed complete identical model YAML profiles, incompatible with the Stage 10 explicitly scoped generation trial. Updated `tests/test_stage8_delivery.py` to assert the two approved knob values while verifying **every other model field remains identical**, preserving revision and concurrency assertions. No change to the checkpoint, model provider, API, production settings, dependencies or previous recorded inference.
- **Real CPU candidate benchmark evidence (user log):** `benchmarks.quality_benchmark run --split dev` completed for five synthetic dev cases × three summary lengths; `benchmarks.stage10_compare` returned **paired=15, changed=0; semantic quality NOT REVIEWED**. This is an observed **NO-GO for the fixed synthetic improvement gates** (identical outputs cannot improve coverage, direction reversals or length differentiation). `review-template` generated unreviewed labels; no candidate semantic scoring completed; no independent human sign-off. No repeat of these 15 model runs is needed.
- **Changed files:** `tests/test_stage8_delivery.py`, `docs/STAGE10_EXPERIMENT_V1.md`, `docs/IMPLEMENTATION_PROGRESS.md` (this entry). **Dependencies:** none. **Tests:** corrected test and full suite not yet rerun on Windows or a complete assistant checkout. Most recent Windows 318/1 remains the only authoritative full-suite evidence until retest.
- **Next stage-10 action:** rerun corrected targeted and full regression; then run *development-only* candidate on the authentic project Markdown dataset and compare to the Stage 9 project baseline. If those outputs remain unchanged or lose essential facts, further isolate map/reduce coverage and avoid promoting the Stage 10 trial. Holdouts remain untouched.


### Stage 10 authentic-project candidate v1 benchmark and per-call tracing (2026-11-01)

- **Stage / Status:** 10 **In Progress**, not complete; user provided actual CPU outputs from `local_stage10_project_dev_candidate_v1.json` and `local_stage10_project_dev_compare_v1.json` with the same fixed reference-project dataset, and confirmed regression test results. Stages 11–13 remain Not Started.
- **User verification:** corrected Stage 8 + provider + comparator targeted tests **40 passed, 1 warning**; full Windows suite **319 passed, 2 deprecation warnings**. The earlier 318/1 failure is resolved. Actual CPU paired comparison on **two real Markdown dev docs** reports **paired=2, changed=2**, both generations successful; holdout untouched.
- **Observed baseline vs candidate:** architecture output 122→65 characters, repeated-fourgram **40%→0%**, reported elapsed 75.247→97.133s; project plan output 61→122 characters, repeated-fourgram 0%→0%, reported elapsed 50.958→69.982s. Not controlled warm latency measurements; no inference speed claim. Candidate model revision remains pinned; no-repeat=3.
- **Expert assistant annotation, NOT independent human sign-off:** **0/6 mandatory facts covered, 6 omitted, 0 distorted** (same as Stage 9). Model outputs only broadly paraphrase document purposes; a new MVP-plan sentence loosely conflates 'Repository source' with 'execution rules' and is provisionally **unsupported (1/3 candidate atomic claims)**. Review interpretation is disputable, but zero fact retention is clear. Therefore **NO-GO for candidate v1 quality promotion**: unchanged **0/15** synthetic dev outputs, zero authentic coverage gain. Repetition sub-gate alone has improved.
- **New code:** `benchmarks/stage10_trace.py` (offline DI-resolved Stage 10 inference-call trace, capped call budget, exact source-quote presence IDs and character/time/repetition metadata, no raw document/summary text persisted, dev-only holdout protection), `tests/test_stage10_trace.py` (new mock-only trace, failure/redaction, holdout and DI restoration tests), `docs/STAGE10_EXPERIMENT_V1.md` and this Progress update. No FastAPI/production pipeline, dependency or model revision change.
- **Assistant isolated tests:** `python -m pytest -q tests/test_stage10_trace.py tests/test_stage10_compare.py tests/test_quality_benchmark.py` **43 passed**, `python -m compileall -q benchmarks tests` passed. **Not Run** after new trace: full Windows suite, real CPU trace on development document, semantic independent review, PDF/DOCX tests, and any holdout. Previous user 319 passed applies to the head **before** trace was added.
- **Next:** after pull and full regression, the user may run `python -m benchmarks.stage10_trace --dataset local_quality_project_v1.json --case-id real_architecture_guide --length medium --output local_stage10_trace_architecture_v1.json` and share the small privacy-minimized report. Trace quote matches are lexical only and must **not** be interpreted as semantic completeness. Then design a single-variable map/reduce or generation ablation based on traced call structure and reviewed evidence. Stage 10 acceptance thresholds stay frozen per `docs/STAGE9_BASELINE_SIGNOFF.md`.


### Stage 10 Windows validation of local inference trace (2026-11-01)

- **Stage / Status:** Stage 10 **In Progress**. User pulled `2a96f0b26ee9b8eb86b2b783c0fa0fa6f23cb4f0` onto Windows `main`, with `env_type=development`.
- **Tests observed on user's Windows virtual environment:** `python -m pytest -q tests/test_stage10_trace.py`: **5 passed** (0.58s); `python -m pytest -q`: **324 passed, 2 nonblocking deprecation warnings** (15.39s). This verifies the full code regression suite on the new trace head, not semantic model quality.
- **Real-model trace command:** `python -m benchmarks.stage10_trace --dataset local_quality_project_v1.json --case-id real_architecture_guide --length medium --output local_stage10_trace_architecture_v1.json` reported successful local JSON creation using the pinned mT5 tokenizer/model. Its **JSON contents have not been supplied**, so call count, quote matches, stage-level behavior and inference timing are **not reviewed or verified** in this progress entry. Do not infer root cause from successful command exit.
- **Changed Files:** this progress record only. **Added Dependencies:** none. **GitHub code changes:** none. **Next action:** inspect user-supplied `local_stage10_trace_architecture_v1.json` before deciding a targeted map/reduce optimization; do not rerun the CPU trace unnecessarily. Frozen Stage 10 quality gates remain unmet; holdout not run.


### Stage 10 authentic architecture map/reduce trace reviewed (2026-11-01)

- **Stage / Status:** 10 **In Progress**. User supplied `local_stage10_trace_architecture_v1.json` after their successful **324 passed / 2 warnings** full Windows regression and **5 passed** trace tests on the preceding head.
- **Actual trace:** 11 calls total: **10 original-source Map** calls spanning the normalized **28,130** characters and **one final Reduce** call. First Map input length 3,051 includes **all 3 pinned exact fact source quotes**; its 65-character output includes none **verbatim**. All ten Map outputs total **677** chars (~2.41% of input); final Reduce input **695** and output **65** chars, no repeated four-grams. Reported full trace elapsed **99.777s**, no error; no observed exact quote in final output.
- **Interpretation / decision:** content was exposed to Map generation, not lost by source-to-chunk omission. Verbatim evidence disappears in Map call 1, but exact-quote absence **does not establish semantic fact omission** in intermediate paraphrases; the final generated text remains low-coverage by prior review. Do not change production logic on lexical evidence alone.
- **Changed Files:** `benchmarks/stage10_first_map_probe.py` (new one-call local-only probe of the first true Map generation; saves generated text only with explicit `--allow-generated-text`, dev-only, no raw source-chunk copy, fails if existing output), `tests/test_stage10_first_map_probe.py` (4 offline tests), `docs/STAGE10_EXPERIMENT_V1.md` and this Progress record. **Added dependencies:** none. **Runtime model/config/API changes:** none.
- **Tests:** assistant isolated `python -m pytest -q tests/test_stage10_first_map_probe.py tests/test_stage10_trace.py tests/test_stage10_compare.py tests/test_quality_benchmark.py`: **47 passed**, and `python -m compileall -q benchmarks tests` passed. **Not Run:** real CPU first-map probe, full Windows suite **after** this new code, PDF/DOCX, holdout, semantic reviewer agreement or Stage 10 acceptance. Last full user-side 324 passing relates to the previous trace head.
- **Next step:** run `benchmarks.stage10_first_map_probe` against `real_architecture_guide` with the local Development dataset and explicit generated-text consent (documented in `docs/STAGE10_EXPERIMENT_V1.md`), review exactly the first Map summary and source-grounded rules, then design a single-variable preservation experiment if warranted. This avoids repeating all 11 model calls merely to view the first Map's result.


### Stage 10 first Map semantic confirmation and dev-only evidence experiment (2026-11-02)

- **Stage / Status:** Stage 10 **In Progress**. The user pulled `cad67be418960faced9b9b119d564b0cef5fb510` and ran tests on Windows: first-map plus trace target tests **9 passed (0.70s)**; full regression **328 passed, 2 nonblocking deprecation warnings (17.13s)**. The `benchmarks.stage10_first_map_probe` CPU run also completed and the user supplied `local_stage10_first_map_architecture_v1.json`.
- **Concrete source-grounded finding:** the first Map input contains all three essential architecture rules in a 3,051-character original source span, but its genuine 65-character / 24-token output says **only that the guide is suitable for transferring architecture standards to ChatGPT or a developer**. None of the three rules is present semantically in this first generated summary. This supports **early Map fact loss** as an observed failure for the architecture document. The 10-map/1-reduce trace still cannot clear the final Reduce stage of other failures.
- **Changed Files:** `src/core/services/summarization/long_text_summarization_service.py` (new `preserve_map_evidence` per-call flag, **False by default**; select up to 3 original-source bullet clauses with general obligation/code/number cues, append only within tokenizer-verified intermediate model output ceiling), `benchmarks/quality_benchmark.py` (dev-only `--preserve-map-evidence` CLI with explicit output metadata; holdouts prohibited), `benchmarks/stage10_compare.py` (report the pipeline ablation flag for paired runs), `tests/test_stage10_map_evidence.py` (new fake-model tests), `tests/test_quality_benchmark.py`, `tests/test_stage10_compare.py`, `docs/STAGE10_EXPERIMENT_V1.md`, and this file. **Dependencies:** none.
- **Technical decision:** Candidate v2 is an **offline single-variable ablation** relative to Candidate v1: same pinned mT5 revision, n-gram=3 and section-aware chunking; the only new option is source-grounded Map excerpt preservation. The ordinary API, production settings, and existing `SummarizationService` calls do **not** enable it. It does not inject benchmark fact IDs or target quotes; its source-extractive heuristic can fail on prose/tables/PDF text, may increase hierarchical depth, and may still lose evidence in the final Reduce stage.
- **Testing:** an assistant isolated source-based selection smoke on the original first architecture excerpt confirmed that the generic extractor identifies obligation and code-style bullet clauses. **Not Run after Candidate v2:** full Windows suite, genuine CPU model outputs, human review of v2 facts, original PDF, holdouts, warm CPU latency or peak RAM. The user's 328 passing tests belong to the **previous first-map-probe head**, not Candidate v2.
- **Decision / next action:** Candidate v1 still **NO-GO** (0/6 required project facts retained). Candidate v2 **NOT EVALUATED**. Run the two already authorized Development project cases with `quality_benchmark ... run --split dev --lengths medium --preserve-map-evidence`, compare against `local_stage10_project_dev_candidate_v1.json`, review generated facts and critical distortions before considering an API rollout. Preserve original Stage 9 frozen quality thresholds; keep holdout untouched.


### Stage 10: candidate v2 scored as NO-GO; offline first-Map evidence replay added (2026-11-02)

- **Stage / Status:** 10 — **In Progress**. The user executed v2 on Windows under `env_type=development`; `git pull` brought `main` to `4ea72bd1bb3fbd467f0214afd92416ab1c314c3d` before testing. Stage 9 remains completed; later stages not started.
- **User-side verification of v2:** `pip check` clean; `compileall` clean; focused Stage 10 tests **64 passed**; full Python suite **336 passed, 2 nonblocking deprecation warnings**. Two actual CPU `medium` Development project-document outputs succeeded. Paired comparator reported **2 pairs, 1 changed**, `semantic_review_status=NOT_REVIEWED`, `candidate_preserve_map_evidence=true`. Holdout untouched.
- **Model output facts:** `real_architecture_guide` remained an **identical 65-character generic purpose sentence**; `real_mvp_plan` reverted to a **61-character generic purpose sentence** from the v1 122-character response. Based on source-grounded assistant review (not independently adjudicated): **0/6** essential target facts retained in both v2 summaries; 6 omitted. No independent new-fact distortion review signed off. Repeat rate remained zero in both final v2 outputs. Candidate v2 is **NO-GO** for Stage 10 development factual-coverage gate `>=3/6`. Final-output behavior cannot tell whether no excerpt was selected, token cap skipped it, or later Reduce lost it; do not claim causal location without intermediate evidence.
- **Files added for follow-up:** `benchmarks/stage10_map_replay.py` (offline replay of the real first-Map generated sentence and current generic source excerpt/cap logic using pinned dev dataset, no `generate` or second model inference, no original or generated text exported); `tests/test_stage10_map_replay.py` (5 synthetic mock-only tests for privacy, provenance and zero model calls). Documents updated: `docs/STAGE10_EXPERIMENT_V1.md`, this Progress file. **Additional dependencies:** none; **API/production/model revision changes:** none.
- **Verification of new replay tool:** isolated `pytest`: **5 passed (0.10s)**; Python compileall passed. **Not run after new tool:** complete Windows tests, real-tokenizer local replay, new candidate inference, independent semantic review and frozen holdout evaluation. The user's 336 passed belongs to the v2 head before the replay files were added.
- **Next:** run `python -m benchmarks.stage10_map_replay --dataset local_quality_project_v1.json --first-map local_stage10_first_map_architecture_v1.json --output local_stage10_map_replay_architecture_v1.json` after update. Inspect only metadata and lexically matched fact IDs before choosing a targeted source-excerpt-cap or Reduce experiment. Stage 10 quality gate not satisfied.


### Stage 10 replay findings and post-Map evidence-trace instrumentation (2026-11-02)

- **Stage / Status:** **Stage 10 In Progress**. Candidate v2 remains **NO-GO** on factual coverage; no new model rollout. The user ran the complete Windows suite after the earlier offline replay addition: **341 passed, 2 nonblocking deprecation warnings**; targeted replay tests **5 passed**, and `compileall` passed. No test failures observed on that earlier head.
- **Source-grounded actual replay result:** pinned `real_architecture_guide`, source dataset SHA-256 `fbc292ba36d07581614810efad42f0585ca9a50605e70a966048c33b9ac63e3c`; first-Map historical output **24 encoded tokens**, three eligible generic source clauses selected and appended, resulting in **88/120 tokens**. All **three** exact pinned fact IDs appeared in the offline *replayed* Map output; **0 additional model calls**. This rules out selected-excerpt and tokenizer-cap failure **for this historical first-Map replay**, not for the actual independent Candidate v2 Map generation. Final Candidate v2 output still omitted all 3 architecture facts.
- **Why more instrumentation was required:** the existing `benchmarks.stage10_trace.CallRecorder` wrapped `Mt5ModelProvider.summarize_async` and therefore saw raw generated Map outputs, **not** the post-inference source-excerpt insertion performed inside the service. Its original per-call records cannot establish whether source facts were actually carried forward to `Reduce` during Candidate v2.
- **Changed Files:** `benchmarks/stage10_trace.py` (add `MapEvidenceRecorder`, conditional `--preserve-map-evidence`, bounded privacy-minimized source/excerpt fact-ID counts and post-Map event metadata, restore temporarily wrapped provider/service methods, prohibit report overwrite), `tests/test_stage10_trace.py` (four mock-only correctness, nonleakage, DI-restoration and type/output-path tests), `docs/STAGE10_EXPERIMENT_V1.md`, and this progress file. **Dependencies:** none. **HTTP/API, production settings and checkpoint:** unchanged.
- **Verification:** after this change, the **full Windows test suite has not yet run** and the **real augmented trace has not yet been produced**; do not conflate prior **341 passed** with new tests. The correctness of the new tracing behavior requires a targeted user-side run. Model quality gates remain unmet, and holdout is untouched.
- **Next action:** user can run `python -m benchmarks.stage10_trace --dataset local_quality_project_v1.json --case-id real_architecture_guide --length medium --preserve-map-evidence --output local_stage10_trace_architecture_v2_map.json` after pulling and testing. Examine `map_evidence_augmentations`, provider call inputs and final output fact IDs to distinguish selection/cap issues from downstream generation loss. See `docs/STAGE10_EXPERIMENT_V1.md` for complete commands and limitations.


### Stage 10 true Reduce omission confirmed; final extractive v3 ablation implemented (2026-11-02)

- **Stage / Status:** **10 — In Progress** (Stage 9 Completed; Stage 11+ not started). The user ran new post-generation diagnostics against real pinned mT5 in Windows Development with `preserve_map_evidence=True`. Targeted trace/replay tests: **14 passed**; complete suite **345 passed, 2 nonblocking deprecation warnings**. This was the pre-v3 head `f595d272234eb1fd7546f8fc8cd7eff70d750670`.
- **Actual trace, source-grounded causal boundary:** ten original-source Map calls, one final Reduce, same model revision/decoder as previous trial. The first Map input included all three architecture rules; the raw generated first Map output did not. After opt-in Map source-clause insertion, the **first Map output contained all 3 exact rules** (`after_chars=304`, `appended_source_lines=3`). The **last provider call input** (`input_chars=2182`, `max_output_tokens=80`) also contained all 3 quotes; its **65-character final output contained zero**. The known generic final sentence also omits them semantically. For this one sample, final Reduce demonstrably discards earlier preserved evidence. Do not extrapolate to other documents or blame extractors. CPU trace completed successfully (reported total `97.569s`), not a controlled latency comparison.
- **New Code / Changed Files:** `src/core/services/summarization/long_text_summarization_service.py` (optional `source_grounded_final=True` **requiring** `preserve_map_evidence=True`, collect original first-level Map source clauses, generate/validate normal Reduce output, then optionally replace it with whole original-source clauses fitting exact final tokenizer budget; default False); `benchmarks/quality_benchmark.py` (Development-only `--source-grounded-final`, pinned run provenance, reject holdout), `benchmarks/stage10_compare.py` (paired candidate provenance), new `tests/test_stage10_final_evidence.py`, updated `tests/test_quality_benchmark.py`, `tests/test_stage10_compare.py`, `docs/STAGE10_EXPERIMENT_V1.md` and this document.
- **Architecture / safety:** No model changes, added dependencies, API/DTO/controller changes, Configuration/YAML changes or background processing. The default service/production call path remains unchanged. Experiment returns original source quotes only when explicitly opted in, with exact tokenizer budget enforcement and no truncation. **Limitations:** introduces an **extractive fallback** which can be incoherent, overprioritize the beginning of a long source, omit contrary/later facts and may never produce an improvement on non-bullet prose. No benchmark fact IDs/expected source quotes are injected, and no claim of proven generalization is made.
- **Verification:** full Windows test suite and real CPU generation **NOT RUN on this new v3 head**. Previous **345 Passed** and raw trace are for previous revision; unexecuted tests must not be called Passed. Next: run full Windows suite, pinned two-document Development v3 trial, paired compare v2-v3, independently review all output facts/claims and assess coherence. Frozen Stage 9 quality thresholds unchanged; holdout untouched. Until this evidence, candidate v3 is **NOT EVALUATED** and remains disabled by default.

### Stage 10: Candidate v3 Windows result and negative-scope extractive safety correction (2026-11-02)

- **Status:** Stage 10 In Progress; Candidate v3 NO-GO due to a critical scope inversion. No release acceptance and no Stage 11 start.
- **User-side evidence:** on the v3 commit, `pip check` clean; compileall succeeded; targeted tests **73 passed**; full suite **354 passed, 2 nonblocking deprecation warnings**. CPU Development runs for both authentic Markdown cases completed, with unchanged dataset SHA and model revision. Paired v2-v3 comparison: **2 paired, 2 changed**, both outputs under the 80-token medium limit; no independently human-reviewed score yet.
- **Assistant provisional coverage:** `real_architecture_guide` **3/3 required rules** verbatim (294 characters, 79 encoded tokens); `real_mvp_plan` **0/3 complete** (TXT and DOCX mentioned but PDF missing, also multi-file and eight-stage facts absent; 214 chars, 80 tokens). Overall **3/6**, matching the numeric development gate but **not** its safety condition. The MVP-plan output incorrectly presents the exact unsupported-.doc bullet, originally under 'خارج از محدوده نسخه اول', as a positive-looking independent statement. This is a critical **section-context/polarity inversion**, not a model-invented quotation. The extra Async convention is off-topic. The last Map/Reduce previous trace finding remains valid.
- **Root cause:** source-only fallback copied a source bullet without retaining its surrounding negative heading. Exact quote provenance alone does not establish faithful interpretation. Candidate v3 is **NO-GO**, regardless of numeric coverage. User annotations remain unreviewed; synthetic gates and holdout remain untested.
- **Changed files (v3.1 limited correction):** `src/core/services/summarization/long_text_summarization_service.py` now excludes bullet evidence within negative-scope Markdown headings, and additionally filters those clauses against the *full original normalized document* before final extractive return even when chunk boundaries split heading from bullet; `tests/test_stage10_final_evidence.py` adds regression checks for nested headings, source-boundary exclusion and English headings; `docs/STAGE10_EXPERIMENT_V1.md` and this Progress document updated.
- **Technical decisions / dependencies:** no new dependencies, no benchmark fact ID hardcoding, no change to normal `summarize_async` defaults, REST API, model lifecycle/parameters, production config, or source normalization; v3.1 remains explicitly opt-in on Development. Negative scope detection is heuristic, limited to recognized Markdown headings; it might miss implicit exclusions or omit legitimate negative-scope warnings.
- **Verification:** the user's **354 passed** refers to v3 before this corrective commit. **Not Run** after v3.1: full Windows tests, model CPU inference, independent human review, PDF/DOCX representative documents, synthetic gate reruns, holdout, controlled warm latency and peak RSS. A cloned full checkout could not be obtained in the assistant sandbox due to unavailable GitHub network DNS; no fabricated test passes.
- **Next:** user pulls `main`, runs targeted and full tests, then executes two fixed Development documents with `--preserve-map-evidence --source-grounded-final`, compares against v3 and checks scope polarity, coverage, coherence. Frozen Stage 9 quality gates remain unchanged.

### Stage 10 v3.1 real benchmark: additional future Backlog scope inversion (2026-11-02)

- **Stage / Status:** Stage 10 In Progress; **Candidate v3.1 NO-GO** despite 3/6 provisional required-fact coverage. User supplied actual CPU Development outputs and v3-v3.1 comparator; the review-template CLI was invoked, but no independently completed reviewer labels were supplied. Holdout remains untouched.
- **Empirical comparison:** v3.1 architecture output is identical to v3 (294 chars / 79 tokens, assistant review **3/3** required rules). v3.1 MVP plan is 183 chars / 79 tokens, different from v3; it mentions TXT, DOCX and length tiers but omits PDF, multi-file support and eight-stage facts (assistant review **0/3** complete). The new line 'OCR برای PDFهای اسکن‌شده.' is sourced **verbatim from future Backlog**, not the implemented MVP. Its missing heading misleadingly implies current support. Paired comparison **2 pairs, 1 changed**, semantic gate NOT_REVIEWED. No controlled timing conclusions. The previous 354 passed suite belongs to v3; v3.1/v3.2 Windows test results have not been provided.
- **Root cause:** source-only fallback ignored a second category of negative context: `## 9. فاز دوم (صرفاً Backlog، نه بخشی از هشت مرحله)`. The initial v3.1 section exclusions recognized `خارج از محدوده` but not future/Backlog. Source-verbatim text alone is insufficient for truthful summaries.
- **Changed Files (v3.2 targeted correction):** `src/core/services/summarization/long_text_summarization_service.py` (_EXCLUDED_SECTION also treats future-work/Backlog headings as non-current; existing whole-original-document scope scan continues across chunk boundaries); `tests/test_stage10_final_evidence.py` (two new tests for future headings and actual project plan's OCR clause); `docs/STAGE10_EXPERIMENT_V1.md` and this progress record. No new dependencies, model or API changes. Default behavior remains opt-out of both extractive experiment flags.
- **Verification:** actual Windows v3.2 full suite and CPU model NOT RUN; assistant independently checked a regex pattern against `IMPLEMENTATION_PLAN.md` and confirmed it identifies the real Backlog heading. That is **not** a full pytest pass. Semantic review and representative PDF/DOCX tests remain pending.
- **Next:** pull, run targeted/full Windows tests, run same two fixed Development documents under v3.2 flags and compare against v3.1. Verify BOTH architecture 3/3 rules and zero misleading .doc/OCR feature claims, then independently annotate facts/claims and revisit diversity/tier synthetic gates. Candidate v3.2 remains NOT EVALUATED; Stage 10 completion and Production rollout blocked.

### Stage 10 Candidate v3.2 Windows results and source-selector diagnostic (2026-11-02)

- **Stage / Status:** Stage 10 **In Progress**; Candidate v3.2 passed the available Windows regression suite and completed the same two authentic development documents, but is **not a production quality GO**. Stages 11–13 not started.
- **Observed Windows verification:** `pip check` clean, Python `compileall` clean, targeted **39 passed**; complete suite **360 passed, 2 nonblocking deprecation warnings (26.70s)**. Latest user run was against prior `ed61e5770f526e642c89f48e933e4a2909e4564f` (before this diagnostic addition). mT5 CPU generated both v3.2 Development summaries, no errors. Same pinned model revision, dataset SHA and split, no holdouts. Paired v3.1→v3.2 comparator **2 pairs / 1 changed / semantic quality NOT_REVIEWED**.
- **Assistant source-grounded preliminary findings:** architecture output unchanged (**294 chars, 79 encoded tokens**), retaining all **3/3** pinned necessary rules. MVP output now **157 chars, 69 encoded tokens**, with previous misleading Backlog OCR excerpt removed, but still **0/3 fully covered**: partial file formats (TXT/DOCX not PDF), no multi-file or eight-stage reference. Overall **3/6 provisional** on the authentic development facts, with no apparent new critical false current capability in these two texts. Extractive sentence fragmentation and inadequate topic coverage remain. Human review incomplete, synthetic frozen gates unmet/not retested, no controlled warm latency or peak RAM.
- **Diagnosis:** source-grounded final trial uses a per-chunk **Markdown-bullet-only** candidate selector plus obligation/code cues and fills the limited final token budget from original source order. The omitted MVP facts appear in its introductory **prose** or project framing rather than selected bullets. This is a plausible mechanism, **not yet proved by direct selector eligibility measurements**; avoid adjusting the model or source expectations without an audit.
- **Changed files:** NEW `benchmarks/stage10_selector_audit.py`, NEW `tests/test_stage10_selector_audit.py` (5 fake DI tests), updated `docs/STAGE10_EXPERIMENT_V1.md` and this Progress file. The new CLI validates Development run provenance and existing source, examines exact quote presence in original text, candidate clauses, full-source eligible clauses and existing generated final result, exports only counts/IDs and does **zero real model inference**. **Dependencies:** none. API/Production/model provider/weights/DI unchanged.
- **Verification after audit code:** isolated pure fake-model **5 passed (0.08s)**, Python compileall succeeded; full Windows suite **NOT RUN** after audit additions; actual tokenizer audit **NOT RUN**. Do not claim 365 passing until user's real run confirms it. Existing 360 Windows Passed remains from previous v3.2 head.
- **Next:** pull and rerun targeted/full pytest, then run `python -m benchmarks.stage10_selector_audit --dataset local_quality_project_v1.json --runs local_stage10_project_dev_candidate_v3_2.json --output local_stage10_selector_audit_v3_2.json`; inspect fact-ID eligibility, especially intro prose. Only then design a controlled, **general-purpose** source extraction candidate; no benchmark-ID hardcoding, Holdout or production activation. Formal Stage 10 acceptance remains blocked.

### Stage 10 v3.2 selector eligibility confirmed; lead-prose preview added (2026-11-02)

- **Stage / Status:** 10 **In Progress**. v3.2 remains development-only, no production quality GO. User pulled prior `337e48339ab684cc7196edce338052834517df2a`, ran targeted **5 passed**, full Windows **365 passed, 2 nonblocking deprecation warnings (28.52s)**, and successful model-free audit with existing pinned dataset and v3.2 raw run; `compileall` passed. This was **before** the new prose preview changes.
- **Actual evidence:** project architecture `10 chunks, 21 eligible clause candidates, 3/3 required facts in original/selected/final`; MVP plan `9 chunks, 24 eligible source bullets, 13 excluded source clauses, 3/3 facts in original but **0/3 selected or final**, and none in excluded clauses. No model inference was performed in the audit. The MVP missing facts never entered the bullet-only selector; adding model tokens or changing Reduce does not address this selection defect directly. Exact-quote matching is a lexical audit, not semantic certification.
- **Changed Files:** `benchmarks/stage10_selector_audit.py` gains `lead_prose_candidates()` and opt-in `--preview-lead-prose`, reporting only count and fact-ID exact-match booleans for possible introductory prose/metadata; `tests/test_stage10_selector_audit.py` gains four tests for prose eligibility, real pinned MVP intro coverage, no output text, invalid-flag rejection; updated `docs/STAGE10_EXPERIMENT_V1.md` and this file. **Dependencies:** none. Model checkpoint, decoder, API, runtime selection, output policy, DI and production settings **unchanged**.
- **Assistant isolated smoke:** read pinned `IMPLEMENTATION_PLAN.md` and checked the exact lead-prose candidate logic using local Python; **17 intro candidate fragments** contain **all 3 MVP source quotes** (file formats, multiple files, eight stages). This is a potential eligibility improvement, **not** an output, budget, or generalization improvement; metadata/fragment context can still mislead and must be reviewed. New code not yet executed as part of the user's actual full repo suite; no claim of extra passing Windows tests.
- **Next:** pull, run new targeted and full pytest, run `python -m benchmarks.stage10_selector_audit --dataset local_quality_project_v1.json --runs local_stage10_project_dev_candidate_v3_2.json --preview-lead-prose --output local_stage10_prose_preview_v3_2.json`, upload metadata-only report. Then design a controlled v4 that preserves the existing architecture 3/3, explicitly checks scope and final tokenizer budget before any new CPU model run. Synthetic/holdout/independent human reviews and Stage 10 acceptance are still pending.

### Stage 10 lead-prose preview verified on Windows; budgeted source-only preflight (2026-11-02)

- **Stage / Status:** Stage 10 **In Progress**. User Windows checkout and tests on prior `e279866a6b9f2818fbb93fb49ae1a3fd3b0ae3a9`: `compileall` clean, targeted **9 passed**, full **369 passed, 2 nonblocking deprecation warnings** (11.75s). Real tokenizer Development lead-prose audit succeeded with **zero** new model inferences. No production release, synthetic acceptance, holdout or independent semantic review.
- **Source-grounded measurement:** architecture: **10 chunks, 21 eligible selected bullets, 3/3 fixed essential facts selected and in final, 2 lead fragments, 0/3 essential facts in lead**. MVP: **9 chunks, 24 eligible selected bullets, 0/3 expected facts selected or in final, 17 lead fragments, all 3 missing fixed facts present verbatim in lead**. This confirms **source evidence eligibility**, not output-token-fit or semantic salience. Existing v3.2 real outputs remain unchanged.
- **Changed Files:** `benchmarks/stage10_selector_audit.py` adds `lead_prose_budget_preflight` and explicit development-only `--preview-lead-budget` flag (requires `--preview-lead-prose`), using real DI provider `count_input_tokens` and service medium final budget to evaluate up to three generic ranked, original-source lead clauses. It exports *only* selected-source count, combined exact token count and fact-ID lexical inclusion booleans, never raw source or generated text; **inference_calls=0**. `tests/test_stage10_selector_audit.py` adds four mock-only tests for selection, joint tokenizer accounting, metadata-only output, type validation and flag compatibility. `docs/STAGE10_EXPERIMENT_V1.md` and this progress file updated. **Dependencies:** none. Runtime service, model, Production and HTTP/API unchanged.
- **Technical decision:** do not yet deploy a mixed prose+bullet v4 Candidate. The source eligibility audit shows potential, but a mixed source summary could disrupt the 3/3 currently retained architecture rules, exceed the 80-token medium final limit, contain stale metadata or invert future/negative-scope claims. Measure budget-fit and lexical survivability first, then decide whether a controlled and genuinely generalizable v4 trial is warranted.
- **Test status:** prior full Windows **369 passed** applies to the previous head only. The **new four budget-preflight tests and actual real-tokenizer preflight have not yet been run on Windows**. Do not advertise them as passed. Runtime inference and holdout NOT RUN.
- **Next action:** pull main, run targeted and full tests, then run `python -m benchmarks.stage10_selector_audit --dataset local_quality_project_v1.json --runs local_stage10_project_dev_candidate_v3_2.json --preview-lead-prose --preview-lead-budget --output local_stage10_lead_budget_preflight_v3_2.json`. Review per-fact budget-fit and compare across both documents before any new experimental Runtime code or CPU inference. Stage 10 quality gates remain unmet/partially evaluated.

### Stage 10 source-span token feasibility audit following real 80-token preflight (2026-11-02)

- **Status:** Stage 10 **In Progress**. Candidate v3.2 **NO PRODUCTION GO**. On prior head `abf61d8f67a2ab8ab11a1b1291f04d6c438baf59`, user Windows: compilation succeeded, focused selector tests **13 passed**, full suite **373 passed, 2 nonblocking warnings** (32.65s). Real tokenizer preflight succeeded, generated **no** mT5 output. Test results for new changes below not yet confirmed on Windows.
- **Actual immutable Development measurement:** Architecture guide lead preview 2 candidate fragments, **0** selected into budget (0/80 tokens), 0/3 pinned facts in lead; architecture facts remain in the separately successful bullet channel. MVP plan 17 lead fragments, **2** chosen within final **76/80** tokens, but only **1/3** essential facts covered verbatim (`file_formats`); `multi_file` and `eight_stages` still absent. Combined with preceding selector audit, missing MVP facts exist in source and prose preview, not in chosen final lead candidates. The 80-token selection wastes capacity on generic purpose text; this is not evidence that the omitted facts cannot be expressed correctly under the existing budget.
- **Changed Files:** `benchmarks/stage10_selector_audit.py` gains optional **`--preview-reference-floor`** dev-only flag requiring both previous lead-preview flags. Only diagnostic: tokenizer counts separate immutable reference source quotes and the joined source-quote span, exports IDs and counts but **never** text. Explicit warning: not a mathematical or semantic minimum for a faithful summary, and benchmark labels must not enter runtime selection. `tests/test_stage10_selector_audit.py` adds 3 fake-provider tests for tokenizer counting, privacy, no inference, validation. `docs/STAGE10_EXPERIMENT_V1.md` and this Progress updated. **Dependencies:** none. Runtime source selection, API, DI, model revision, generation/config and Production unchanged.
- **Testing and blockers:** full Windows suite **NOT YET RUN** with source-span audit addition; standalone helper and 3 new tests committed. Latest prior 373 passed are not attributed to the new commit. **Not Run:** new real-tokenizer quote-cost report, Candidate v4 CPU test, independent semantic assessment, holdout and frozen synthetic gates. Stage 10 remains blocked on trustworthy topical coverage and zero critical inversions.
- **Next:** run `python -m benchmarks.stage10_selector_audit --dataset local_quality_project_v1.json --runs local_stage10_project_dev_candidate_v3_2.json --preview-lead-prose --preview-lead-budget --preview-reference-floor --output local_stage10_reference_floor_v3_2.json` following `git pull`, new targeted/full regression and compileall. Use these numbers to design **general source-claim selection with diversity and context preservation**, not a benchmark fact-injecting candidate. Keep reference gate thresholds unchanged.

### Stage 10 actual source-quote budget and guarded Candidate v4 (2026-11-02)

- **Stage / Status:** Stage 10 **In Progress**, v4 **Not Evaluated**, production **NO-GO**. On prior head `cc1db2db43b84061fee17b3109f7b5fedb06d560`, Windows `compileall` passed, targeted selector tests **16 passed**, full suite **376 passed / 2 nonblocking warnings** (19.64s). User ran real tokenizer-only reference-span audit successfully on two fixed Development cases; **inference_calls=0**. These results are **pre-v4**, not new runtime tests.
- **Verified audit result:** immutable architecture three source quotes use **52 tokens jointly** under medium 80; all three were already bullet-eligible and in v3.2 final. Immutable MVP three source quotes jointly use **45 tokens** under 80, but old lead selection selected **two longer sentences at 76/80 tokens**, with **1/3** facts (`file_formats`) and no `multi_file`/`eight_stages`. Source_quote spans are incomplete benchmark labels, **not valid summary targets or semantic-token lower bounds**. Their contents are not consumed by runtime logic. This measures deficient evidence ranking/budget allocation rather than proving all three complete original sentences can fit.
- **Changed Files:** `src/core/services/summarization/long_text_summarization_service.py` introduces optional **`balanced_source_final=True`** requiring both previous v3.2 flags, scoring whole original preface/first-major-section source sentences with generic capability, quantity and code-marker signals and score-per-token ranking; it checks the actual tokenizer on the full resulting extractive string under the unchanged output budget and falls back to existing v3.2 bullet strategy when no lead fits. `benchmarks/quality_benchmark.py` exposes Development-only `--balanced-source-final` and serializes its setting, refusing holdouts. `benchmarks/stage10_compare.py` records baseline/candidate v4 provenance. New `tests/test_stage10_balanced_final.py` covers original-source excerpts, nested excluded sections/code fences, fallback, validation and holdout. `tests/test_quality_benchmark.py` and `tests/test_stage10_compare.py` cover opt-in propagation and pairing. `docs/STAGE10_EXPERIMENT_V1.md` and this Progress file updated.
- **Architecture / risk:** no dependencies, model revision, generation configuration, REST API/DTO, DI or default Production behavior changed. All three flags are off by default. This is source-extractive output, **not** an abstractive fidelity fix. Ordinary-prose negative context and representativeness remain unproven. The original Map and Reduce model calls still occur in the v4 trial; no hidden data or benchmark fact IDs are used by the ranker.
- **Test status:** local Windows **full suite, new targeted tests and actual CPU v4 inference NOT RUN** after implementation. Do not claim 376 or any new tests Passed on the new head; 376 belongs to the old diagnostic. Holdout, synthetic gate rerun, independent human semantic adjudication, controlled warm latency/RSS still not run. Stage 10 acceptance not met.
- **Next action:** `git pull --ff-only origin main`, compileall, run `tests/test_stage10_balanced_final.py`, relevant regressions and full suite. Then run the fixed 2-document Development benchmark with `--preserve-map-evidence --source-grounded-final --balanced-source-final`, compare against `local_stage10_project_dev_candidate_v3_2.json`, independently review facts, polarity, completeness and readability. Keep all frozen gates unchanged. Candidate v4 remains NO-GO for production until reviewed.

### Stage 10 Candidate v4 Windows tests and preliminary 5/6 coverage (2026-11-02)

- **Stage / Status:** **10 In Progress**; Candidate v4 has promising two-document Development results but is **NOT approved for Production**. No further heuristic or model runtime changes were made after the user's v4 run; frozen Stage 9 criteria, model revision and experimental default-off flags remain intact.
- **Windows user verification on v4 head `f6698cce626eae3038c62204c9b0210756e5fa5e`:** `pip check` clean; `compileall` clean; targeted **82 Passed** in 6.31s; complete suite **386 Passed, 2 nonblocking deprecation warnings** in 23.18s. Two actual mT5 CPU Development inference workflows completed successfully. Pinned dataset SHA-256 `fbc292ba36d07581614810efad42f0585ca9a50605e70a966048c33b9ac63e3c`. Paired v3.2-v4 comparison **2 paired, 1 changed**, model and decoder settings identical, semantic status `NOT_REVIEWED`. Baseline v3.2 remains unchanged.
- **Assistant's preliminary source-grounded review (not independent human signoff):** `real_architecture_guide` byte-identical to v3.2 (294 characters, 79/80 medium tokens), retains **3/3** original mandatory rules. It also includes an incomplete fourth excerpt ending in `نساز؛`, reducing readability and possibly context. `real_mvp_plan` now two complete original-source sentences (177 characters, 66/80 medium tokens) containing **TXT, PDF, DOCX** and **multi-file request with separate summaries**, so **2/3** required facts; `eight_stages` still omitted. Combined provisional result: **5/6 facts covered**, **1/6 omitted**, no obvious semantic inversion among the two outputs; both have zero four-gram repetition. Numeric fixed authentic Development threshold >=3/6 is met only provisionally. Nine source-supported claim annotations are drafted, not validated by independent review. Do not claim production faithfulness or a measured speed gain (133.702s and 88.104s are single noncontrolled CPU times). Peak RAM not measured.
- **Files changed in this handoff:** `docs/STAGE10_EXPERIMENT_V1.md` updated with actual v4 results, risk analysis and reviewer handoff; this `docs/IMPLEMENTATION_PROGRESS.md` updated. **No new dependencies, source/runtime/DTO/API/infrastructure or test changes this turn**. Outside GitHub, created an `assistant_draft` review JSON matching the immutable v4 run hash for human verification; it must not be committed and is not itself an independent review.
- **Verification / gates NOT RUN:** independent human approval of each fact label and atomic claim; v4 fixed synthetic Development cases across `short`, `medium`, `long` (frozen >=8/19 facts, 0 critical direction/number flips, <=12.5% unsupported, >=3/5 tier difference); representative TXT/PDF/DOCX third-party documents; reserved synthetic and real holdouts; controlled warm performance/peak RAM. These remain blocking for an overall Stage 10 GO.
- **Next readiness:** user independently validates the existing v4 review template or the assistant draft against original documents, saves `local_stage10_project_dev_review_v4_validated.json`, then uses `python -m benchmarks.quality_benchmark --dataset local_quality_project_v1.json score --runs local_stage10_project_dev_candidate_v4.json --reviews local_stage10_project_dev_review_v4_validated.json --output local_stage10_project_dev_score_v4.json`. Evaluate frozen synthetic Development gates next with the v4 flag enabled on `benchmarks/fixtures/quality_v1.json`; do not unlock holdout or enable default API before all gates are met. Stage 10 remains **In Progress**.

### Stage 10: v4 score computed from copied assistant draft; synthetic Development next (2026-11-02)

- **Status:** Stage 10 **In Progress**, Candidate v4 **provisional Development only / Production NO-GO**. The user's first `score` attempt failed with `FileNotFoundError` for `local_stage10_project_dev_review_v4_validated.json`. User then **copied the assistant's draft** to that name and reran the tool successfully: `reviewed=2`, `unreviewed=0`. The file-copy action is NOT independent review; the CLI validates completeness/schema, not reviewer identity or correctness.
- **Score values from uploaded `local_stage10_project_dev_score_v4.json`:** 2/2 successful medium-source runs; **5 covered / 1 omitted / 0 distorted (83.33% fact coverage)**. All 3 `action` and both `topic` reference facts covered; the omitted `number` fact is `eight_stages`. From 9 claims in the copied assistant draft, **0 unsupported**; 0.0 four-gram repetition on both outputs; medium 72.5 mean encoded tokens, 0/2 exceeding the 80-token ceiling. `short` and `long` have count=0, so length variation remains NOT EVALUATED. The dataset hash remains `fbc292ba36d07581614810efad42f0585ca9a50605e70a966048c33b9ac63e3c`.
- **Interpretation / limits:** this is a mechanically valid score of assistant-supplied provisional labels, **not independently human-validated** despite the filename and `reviewed_runs` count. The architecture output still contains an incomplete trailing excerpt. No claims that general accuracy, production readiness, latency or external-document performance is proven. Previous verified Windows v4 suite remains **386 Passed / 2 deprecation warnings**; no new tests executed with this documentation-only change.
- **Files changed:** `docs/STAGE10_EXPERIMENT_V1.md` records exact metrics and workflow; this `docs/IMPLEMENTATION_PROGRESS.md` records provenance and blockers. No new dependencies, model, decoder, controller, API or algorithm edits. Prior holdout untouched.
- **Next Stage / readiness:** keep Candidate v4 locked for a separate 5-document, 3-tier **synthetic Development** trial (`benchmarks/fixtures/quality_v1.json`, flags `--preserve-map-evidence --source-grounded-final --balanced-source-final`, `--split dev`). Generate an unreviewed review template, independently annotate atomic claims/coverages, and test frozen gates: >=8/19 medium unique facts, 0 critical direction/date/number/person inversions and 0/19 distorted, <=12.5% unsupported claims and >=3/5 distinct short/long outputs. Independent human verification of the original two real-document runs remains outstanding. No Stage 10 GO, holdout release or Production activation until these gates are satisfied.

### Stage 10: v4 synthetic Development exposes critical regressions — NO-GO (2026-11-02)

- **Stage / Status:** Stage 10 **In Progress / quality Blocked**. The user uploaded real v4 CPU run `local_stage10_synthetic_dev_candidate_v4.json` with 5 synthetic Development sources × 3 length tiers = **15 successful executions**; unchanged dataset SHA-256 `cc907d6b16a4b68685b280002bb0a0f550ce6ce3966941c8732702c016f8a9a9`, model revision `b575560ad967050e77a40f907abb1ebbeefb9a15`, single-worker CPU, and all three experimental flags enabled. Holdout cases were not run. No independent review or scored synthetic facts provided.
- **Exact structural result:** **0/5** sources have distinct short vs long text; all three tiers are byte-identical for every Development source, with encoded token counts **26, 33, 22, 19, 22** respectively, well below the 40-token short ceiling. Frozen length gate >=3/5 **FAILED**. No output violates configured tier caps.
- **Assistant provisional source-fact assessment (NOT official CLI score):** across five unique `medium` sources, **3/19 covered, 14/19 omitted, 2/19 distorted**: `pollution_decrease` is reversed to an *increase* in pollution; `support_up` is reversed to a *decrease* in software support costs despite 30→36 million rise. Those are the **same two critical direction failures** as Stage 9. Frozen medium coverage >=8/19 and zero critical distortion both **FAILED** on preliminary review. Driver advice, other multitopic subjects, teacher training/infrastructure/phasing, meeting owners/follow-up/budget and network/contract facts are omitted. The weather summary says `هشدار داد` rather than source `اعلام کرد`, a potential unsupported attribution that requires reviewer adjudication; unsupported-claim rate is **NOT SCORED**.
- **Root cause in examined code:** v4's `balanced_source_final` branch only runs after hierarchy when `first_level_source_evidence` is nonempty. Four short direct single-input prose cases bypass the experimental extractive final branch. The long repeated education input contains no Markdown bullets, so first-level source evidence stays empty and the experimental final is also bypassed. Consequently the new heuristic cannot be expected to repair these direct-text semantic inversions or tier sameness. Do not interpret favorable 5/6 source-document extraction as proof of general-purpose Persian abstractive accuracy.
- **Changes / dependencies:** only `docs/STAGE10_EXPERIMENT_V1.md` and `docs/IMPLEMENTATION_PROGRESS.md` updated with verified raw-run metadata, provisional error taxonomy, frozen gate decisions and reviewer workflow; **no new dependencies, model tuning, runtime/API changes or tests**. Prior actual v4 Windows test suite remains **386 passed, 2 nonblocking warnings**, not rerun after docs-only changes.
- **Acceptance / next:** Candidate v4 **NO-GO** for Stage 10 completion or Production; frozen real Markdown assistant-draft review is 5/6 but not independent human validation. Run `benchmarks.quality_benchmark review-template` on synthetic v4 raw file, obtain independent fact and atomic-claim labels across all 15 outputs, and `score` only after actual review. Further engineering should directly address ungrounded mT5 direction/number generation on plain text and real short/medium/long differentiation, without overfitting to Markdown intros. Representative TXT/PDF/DOCX, warm CPU memory/latency, both holdouts and Stage 10 acceptance remain pending.

### Stage 10: source-grounded v5 extractive ablation implemented, quality still blocked (2026-11-02)

- **Status:** Stage 10 **In Progress / Quality Blocked**, Candidate v4 remains **NO-GO**, Candidate v5 **NOT EVALUATED**. The last confirmed Windows v4 full suite is **386 Passed, 2 nonblocking warnings**; new v5 tests are **not yet run** on Windows or the real checkpoint. Two holdout splits remain locked.
- **Motivation / unchanged evidence:** v4 frozen synthetic Development run consists of 5 unique sources × 3 tiers with all tier outputs identical (0/5); preliminary 3/19 medium facts covered, 14/19 omitted and two critical inversions (pollution decrease→increase; support expense rise 30→36 wrongly called decrease). v4 also had 5/6 real Markdown Development coverage based on an assistant draft, **not independent human validation**. A separate, hash-bound `local_stage10_synthetic_dev_review_v4_assistant_draft.json` was created outside GitHub for all 15 outputs (potentially unsupported `هشدار داد` marked for adjudication); user must independently review the claims and labels before scoring.
- **Files Changed:** `src/core/services/summarization/long_text_summarization_service.py` adds opt-in `source_sentence_final` source-only extractive alternative for both direct and long texts. It emits complete original sentences, maintains original order, deduplicates, filters fenced Markdown and heading-based out-of-scope sections, uses bounded candidate ranking/paragraph diversity and token-exact max 1/3/6 sentences for short/medium/long, and **fails closed** if none fits. `benchmarks/quality_benchmark.py` exposes dev-only `--source-sentence-final` with explicit `inference_mode=source_sentence_only_no_model_generate`; `benchmarks/stage10_compare.py` records v5 provenance. New `tests/test_stage10_source_sentence_v5.py`, plus updates to `tests/test_quality_benchmark.py` and `tests/test_stage10_compare.py`, exercise parent flags, holdout refusal, source-verbatim direction/numbers, tier budgets, Markdown scopes and model-free behavior. `docs/STAGE10_EXPERIMENT_V1.md` and this progress updated. **Dependencies:** none.
- **Design and limitations:** This is a **no-generate extractive ablation**, not a fix to mT5 semantics and not a production policy. It may lose cross-sentence context or later topic coverage due to the 64-sentence candidate cap and is not an independent semantic fact verifier. `@inject`, existing DI and normal API remain unchanged; all experiment flags default to False. Checkpoint/revision/generation settings, frozen facts, acceptance thresholds and both holdouts unchanged. No model/CPU run for v5 has been claimed.
- **Tests:** latest reported pre-v5 Windows `pip check` and `compileall` passed; targeted 82 tests passed; full 386 tests passed on the v4 head. **New v5 focused/full Windows tests NOT RUN**, real-tokenizer inference-free v5 run NOT RUN, human Synthetic v4 review NOT independently completed, and full synthetic/real Stage 10 gates NOT PASSED. Do not substitute source quotation presence for output-quality acceptance.
- **Next steps:** pull `main`, run Python compileall and new focused/full pytest. Next run five synthetic Development sources for short/medium/long using `--preserve-map-evidence --source-grounded-final --balanced-source-final --source-sentence-final`, generate `local_stage10_synthetic_dev_candidate_v5_extract.json` and paired comparator against v4. Obtain independent review, score unchanged frozen gates, and verify representative TXT/PDF/DOCX before any further GO decision. Stage 10 remains not completed.

### Stage 10: v5 Windows regression and pairwise commands passed; semantic status pending (2026-11-02)

- **Stage / status:** Stage 10 **In Progress / Quality Blocked**, v5 source-extractive Dev trial run completed but **semantic quality NOT REVIEWED / Production NO-GO**. GitHub prior implementation SHA `77bc1b1548cb9eb6656c9260027177b8a32c1b52`; user Windows `git pull --ff-only` fast-forward succeeded.
- **Passed Windows commands:** `pip check`: no broken requirements; `compileall` clean; new/related focused suites **80 Passed (4.86s)**; complete regression **398 Passed, 2 pre-existing deprecation warnings (24.94s)**. These are genuine user-observed results, not reruns inside the assistant environment.
- **Run and compare:** synthetic CC0 `quality_v1.json`, `--split dev --lengths short medium long` with v5 four opt-in flags completed, output `local_stage10_synthetic_dev_candidate_v5_extract.json`. v4-v5 pairwise comparator output `local_stage10_synthetic_dev_compare_v4_v5_extract.json`: **15 paired, 15 changed**, explicit `semantic quality NOT REVIEWED`. As the raw reports have not yet been uploaded in the present turn, no per-fact or per-tier v5 metric is confirmed. Change rate is not quality.
- **Changed files:** `docs/STAGE10_EXPERIMENT_V1.md` and `docs/IMPLEMENTATION_PROGRESS.md` only, to record actual user-side verification and unresolved quality evidence. No runtime, tokenizer, model, Controller/API, dependencies, acceptance thresholds or fixture changes.
- **Pending gates:** upload v5 raw run and comparison for real output inspection; independent claim/fact review; source text direction/number/time/negation fidelity; >=8/19 unique synthetic medium facts, zero critical distortions, <=12.5% unsupported claims, >=3/5 distinct short vs long outputs, and previously established real Development constraints. Both reserved holdouts remain untouched; no Production default change.
- **Next:** inspect two v5 JSON files, create an **unreviewed** Review template if needed, obtain actual independent annotations and run the score CLI. Do not proclaim Stage 10 completion, model accuracy, or performance superiority from passing tests/15 changed strings.

### Stage 10: v5 source-extractive Development outputs inspected; 11/19 medium quotes (2026-11-02)

- **Stage / status:** Stage 10 **In Progress / Quality Blocked**. User uploaded the actual v5 synthetic Development raw run and paired v4-v5 comparator. Candidate v5 is an **extractive-only ablation** (`inference_mode=source_sentence_only_no_model_generate`); model generation is bypassed, so no claim of improving mT5 weights or direct abstractive reliability. No changes to Production flags, model revision, frozen dataset, acceptance gates or either holdout.
- **Verified artifact provenance:** synthetic CC0 dataset SHA-256 `cc907d6b16a4b68685b280002bb0a0f550ce6ce3966941c8732702c016f8a9a9`; v5 run canonical SHA-256 `9753e81679f6bd9a33db1958d2d1a26666f90bcdb7d0accb456d32ca78a585f7` matches comparator's `candidate_runs_sha256`. All 15/15 outputs succeeded and fit their exact 40/80/120 short/medium/long token ceilings; v4-v5 comparator confirms 15/15 changed text and no repeated four-grams. Previous Windows test verification on v5 head **398 passed, 2 deprecation warnings**, focused **80 passed**, `pip check` and `compileall` clean.
- **Per-source medium exact reference spans:** weather 2/2; multitopic pollution 2/5; repeated education 2/4; meeting 3/5; budget report 2/3. Combined **11/19 source-quote matches (57.89%)**; `short` 4/19 and `long` 18/19. These are literal excerpt matches, **not independently human-reviewed semantic facts**. `short` differs from `long` for **5/5**, meeting frozen >=3/5 observable length gate. The prior critical direction inversions (pollution decrease→increase; software support expense 30→36 rise falsely rendered as decrease) are **not present** in the source-verbatim medium outputs, although pollution-reduction aim is OMITTED there. No obvious unsupported claim observed in the extracted strings; independently reviewed unsupported-claim rate remains **NOT SCORED**. The source-extractive approach may drop qualifiers/context, does not guarantee 0/19 semantic distortion on arbitrary documents, and is not a polished abstractive summary.
- **Remaining deficits:** incomplete medium coverage of 8/19 source facts, long still missing underserved-neighborhood clinic location, indistinct weather medium/long, capped 64 candidate sentences, punctuation-only sentence eligibility, and no independent evaluator for 15 outputs. Cold-start tokenization took 73.238s on the first v5 run and later trial calls were short; not a controlled warm end-to-end latency comparison, and no peak RSS measurement.
- **Changed files in this assessment:** `docs/STAGE10_EXPERIMENT_V1.md` and this `docs/IMPLEMENTATION_PROGRESS.md` only. No code or test changes, no dependencies. The last 398 Passed result belongs to v5 code pre-documentation. These documents update observed result, threshold interpretation and remaining blockers.
- **Next:** create `benchmarks.quality_benchmark review-template` for `local_stage10_synthetic_dev_candidate_v5_extract.json`, independently label 19 source facts and all atomic claims over five sources × three tiers, then `score` only after genuine review. Decide whether a distinct opt-in Extractive mode should coexist with abstractive mT5 before general release; evaluate permitted authentic Persian TXT/PDF-text/DOCX and controlled CPU/memory prior to Production approval. Do not unlock holdout or label Stage 10 Completed based on two tiny Development datasets.

### Stage 10: v5 synthetic provisional assistant review score validated by CLI (2026-11-02)

- **Status:** Stage 10 **In Progress / quality NOT independently signed off**, source-only Candidate v5 **provisional Development success, Production NO-GO**. User executed `benchmarks.quality_benchmark score` successfully with assistant-drafted labels `local_stage10_synthetic_dev_review_v5_assistant_draft.json`; tool output `local_stage10_synthetic_dev_score_v5_provisional.json` uploaded and inspected. `reviewed=15` is mechanical annotation completeness, not independent human verification.
- **Provisional metrics:** 15/15 successful synthetic Development results; 49 assistant-segmented claims; **33 covered / 24 omitted / 0 distorted fact labels** (57 = 19 frozen reference facts × 3 requested tiers), **0/49 unsupported claims according to assistant labels**. Tier-specific covered facts: **short 4/19, medium 11/19 (57.89%), long 18/19**; 0 outputs over respective exact tokenizer ceilings (mean 30.0/40, 61.6/80, 86.0/120), no four-gram repetition; all **5/5** source texts have different short and long outputs. Dataset SHA `cc907d6b16a4b68685b280002bb0a0f550ce6ce3966941c8732702c016f8a9a9` matches the v5 runs; immutable v5 run hash `9753e81679f6bd9a33db1958d2d1a26666f90bcdb7d0accb456d32ca78a585f7` matches assistant draft and pairwise comparator.
- **Gates / interpretation:** numeric frozen Development >=8/19 medium, zero labeled critical directional inversion, <=12.5% labeled unsupported, >=3/5 distinct short-vs-long are **provisionally met by assistant labels**, NOT independently adjudicated. v5 bypasses mT5 `generate` entirely (`source_sentence_only_no_model_generate`) and is an extractive baseline, not a verified improvement of model generation or a production-ready default. Context/negation loss and broad Persian document generalization are still untested; no holdout access.
- **Code / files / tests:** no new source/API/model/dependency/test changes. This documentation-only update modifies `docs/STAGE10_EXPERIMENT_V1.md` and `docs/IMPLEMENTATION_PROGRESS.md`. Last user-confirmed v5 Windows tests **398 Passed / 2 deprecation warnings**, previous focused **80 Passed**, pip check/compileall clean. No tests rerun for this docs-only update.
- **Next:** have an *independent* reviewer verify all 57 fact-tier labels and 49 atomic claims against original evidence; then save a truly verified review under a separate path and score. Keep frozen sample split, both holdouts, thresholds, model revision and REST API defaults unchanged. Evaluate authentic TXT/PDF/DOCX, multi-section/negation examples and controlled CPU memory/timing, and decide explicitly whether an optional extractive path is compatible with the original mT5 abstractive objective before any Stage 10 completion/Production GO.

### Stage 10: three-format Persian sample received; PDF RTL/line-wrap preliminary blocker (2026-11-02)

- **Stage / status:** Stage 10 **In Progress / NO-GO**. User uploaded `persian_test.txt`, `persian_test.docx` and `persian_test.pdf`; these are *one identical authored source in three file formats*, not three independent real-world documents. Files were assessed locally but NOT added to GitHub or the frozen benchmark dataset. Independent human review of synthetic v5 is still pending.
- **Initial extraction assessment:** local TXT UTF-8 baseline 3,069 characters; python-docx paragraph text 3,055 characters (same content after collapsing whitespace); two-page text PDF raw pypdf layout text has reversed RTL order. A local code-equivalent copy of the repository `_restore_visual_rtl_text` repaired most PDF order (3,103 characters), but PDF hard line wraps, loss of Persian ZWNJ/diacritics and a few rendering artifacts remain. Exact-match anchors on 10 chosen source phrases: TXT **10/10**, DOCX **10/10**, PDF post-correction **6/10**. The local comparison used **pypdf 5.9.0**, whereas the project requires **pypdf >=6.21.2**; Windows service behavior is **NOT YET VERIFIED**. These provisional percentages are only extraction diagnostics, not fact coverage or actual mT5 summaries.
- **Root-cause risk:** opt-in v5 `_source_sentence_candidates` splits source by physical lines, so layout-wrapped PDFs can produce truncated sentence fragments ending in punctuation, breaking negation and context even though text is copied verbatim. The sample also embeds `احتمال نشتی...` and `نشتی ... تأیید شد` as contrasting *hypothetical quotes*; an extractor must not report the latter as a confirmed real event.
- **Changed files:** `docs/STAGE10_EXPERIMENT_V1.md` and this `docs/IMPLEMENTATION_PROGRESS.md` only; no code, API, dependencies, checkpoint, stage thresholds or tests changed. No Windows tests rerun; most recent user-confirmed full suite is **398 passed, 2 warnings**, source-extractive synthetic provisional **11/19 medium facts** under assistant annotations, not independent review.
- **Next required local check:** use the existing `benchmarks.quality_benchmark inspect-extraction` with an exact anchor file and each original TXT/DOCX/PDF, record `exact_anchor_recall`, counts and false-negative examples from *repository's pinned environment*. Only then consider a targeted regression fix for PDF sentence assembly (with fake-provider tests and no Production flag change); independently review candidate summaries and eventually collect representative authorized distinct TXT/PDF/DOCX samples. Holdout remains sealed.

### Stage 10: PDF layout-wrapped sentence assembly fixed in opt-in v5 (2026-11-02)

- **Status:** Stage 10 `In Progress / Quality Blocked (NO-GO)`. The three user-provided `persian_test.txt/.pdf/.docx` files are one identical test document in three containers, not distinct representative documents. Neither the synthetic nor the real holdouts were accessed.
- **Root cause:** `src/core/services/summarization/long_text_summarization_service.py::_source_sentence_candidates` selected punctuation-terminated **physical lines**, which is unsafe when pypdf `layout` text places blank spacer rows between fragments of a single logical sentence. The old v5 selector could return orphaned fragments such as `شود و خواننده ...` without the preceding context. A standalone local preflight on the actual uploaded PDF's earlier RTL-repaired text reproduced the fragments.
- **Implementation files:** updated `src/core/services/summarization/long_text_summarization_service.py` only in the **opt-in** `source_sentence_final` parsing path. It accumulates text across one blank spacer for unfinished sentences, flushes on two blank spacers/completed sentences and before Markdown headings/excluded sections/fences/bullets/tables, and skips standalone PDF numbered headings. `_MAX_SOURCE_SENTENCES`, exact tokenizer budgets, DI, default mT5 API and checkpoint are unchanged. Because joining a PDF display wrap inserts a space, candidates are source-derived whitespace-normalized sentences, **not guaranteed byte-for-byte exact source substrings**. It is not a semantic verifier or a fix for lost PDF ZWNJs.
- **Tests created:** three focused regression cases appended to `tests/test_stage10_source_sentence_v5.py`, exercising PDF blank spacer wraps with numbered headings, two-blank and excluded-section boundaries, and quoted hypothetical/negation preservation. No dependencies added and no user files committed into the repository.
- **Local preflight run:** independently reassembled a copy of the local corrected PDF text using the same blank-spacer/heading logic and obtained 33 complete sentence candidates with **zero** of the two previously observed orphaned prefix fragments. This environment has `pypdf 5.9.0` whereas the repository declares `pypdf >=6.21.2`; this is a **targeted offline algorithm preflight, not an end-to-end service test**. Full `pytest` and pinned-version PDF extraction tests have **NOT** been run since this fix; the last confirmed Windows full suite was **398 passed, 2 warnings** on the preceding code head.
- **Next:** user pull `main`, run targeted and full pytest in installed Windows `.venv`, then run existing `quality_benchmark inspect-extraction` for the three local files using the previously supplied 10 UTF-8 anchor lines. Upload exact diagnostic JSONs and log. Review semantic context/hypothetical quotation and gather distinct authorized Persian documents before any Stage 10 GO. Frozen thresholds and independent human review requirement remain unchanged. No Production rollout.


### Stage 10: v5 Windows regression correction — raw PDF paragraph boundaries (2026-11-02)

- **Stage/Status:** 10 — In Progress / Quality Blocked (NO-GO). No Production behavior, model checkpoint, decoding setting, DI registration or Stage 9 acceptance gates changed.
- **User-reported Windows baseline:** `git pull --ff-only origin main` fast-forwarded to `851b304b445d47c23cefe5e6d5cd27958197175f`; `pip check` passed. Focused suites: **88 passed, 1 failed**; entire suite: **400 passed, 1 failed, 2 nonblocking warnings**. Failure: `test_v5_rejoins_pdf_display_wrapped_sentence_across_single_blank_spacer`.
- **Confirmed root cause:** `TextChunkingService.normalize()` folds three consecutive newline characters to two. The experimental `_source_sentence_candidates()` relies on two blank spacer lines to end an unfinished paragraph. Feeding normalized text caused an unpunctuated PDF title to be joined with a subsequent valid sentence despite the direct-parser test passing.
- **Targeted correction:** `src/core/services/summarization/long_text_summarization_service.py` now passes original, validated text to the opt-in `source_sentence_final` path, preserving paragraph spacing; adds a raw character-budget guard to avoid work-budget bypass when normalizing large whitespace inputs. `tests/test_stage10_source_sentence_v5.py` adds a regression for that resource bound, retaining the previously failing PDF case. Dependencies: **none**.
- **Preflight:** isolated Python reproduction confirmed the source-versus-normalized paragraph behavior and expected boundary correction. This is **not a complete real-repository pytest pass**. New focused/full Windows tests and representative TXT/PDF/DOCX checks: **Not Run after correction**; require local confirmation.
- **Local-only benchmark issue:** `inspect-extraction` failed before extraction because the user did not have `persian_stage10_anchors.txt` locally. All three diagnostic JSON outputs were absent; the later wildcard `Get-Content -Raw` error cannot be used to infer extraction failure. The UTF-8 anchors file must be prepared by the user from exact passages of the authorized documents; it must not be committed with local document data.
- **Follow-up:** pull updated `main`, rerun focused and full pytest, prepare local exact anchors, run `inspect-extraction` for each supported format, review recall and source-grounded output against originals. Stage 10 quality promotion remains blocked until actual reviewed evidence meets the frozen gates.


### Stage 10: Windows verification and three-format extraction diagnostics (2026-11-02)

- **Stage / status:** 10 — In Progress / Quality Blocked (Production NO-GO). User pulled correction commit `b9a12355dd0cd228a7f22dd082de4287f5b615c9` on `main` and confirmed the local HEAD matches. This is a verification record only; no extraction/parser/model/API behavior changed.
- **Windows regression results:** `pip check` passed; `compileall -q src benchmarks tests` passed; focused extraction/v5/hierarchy suites **90 passed (9.99s)**; complete test suite **402 passed, 0 failed, 2 nonblocking dependency deprecation warnings (24.35s)**. This closes the prior v5 PDF-paragraph regression observed as 400/1 at the preceding head.
- **Real local sample extraction diagnostic:** the user created 10 UTF-8 source anchors from `persian_test.txt` and ran `benchmarks.quality_benchmark inspect-extraction` against three file containers containing the same authored Persian document. Exact substring recall: **TXT 10/10 (1.0), 3069 chars; DOCX 10/10 (1.0), 3055 chars; PDF 4/10 (0.4), 3098 chars**. All three diagnostics were written. The PDF parser printed `Xref table not zero-indexed. ID numbers for objects will be corrected.` but completed successfully.
- **Interpretation:** benchmark `exact_anchor_recall` counts literal `phrase in extracted` checks. It does not establish that 60% of PDF content is lost, that the PDF has semantic distortions or that a summary is accurate. Layout newlines, RTL repair, ZWNJ, glyph and font encoding differences remain competing explanations; inspecting the six missing exact matches is required before an extraction patch.
- **Follow-up:** locally classify the six PDF anchor misses using whitespace-insensitive and ZWNJ-insensitive comparisons without printing the private source. Escalate only unmatched cases to authorized local raw-text comparison and a minimal extractor regression fixture. Record whether the real PDF preserves negation, numeric direction and hypothetical quotations; independently review Stage 10 extractive outputs before any Production GO. Holdouts remain untouched.


### Stage 10: exact anchor miss classification on the authentic Persian PDF (2026-11-02)

- **Stage / status:** Stage 10 remains In Progress / Quality Blocked (Production NO-GO). This is a diagnostic update only, without changing extraction behavior, the opt-in v5 summarizer, model settings or acceptance criteria.
- **User-reported local diagnostic:** The same ten TXT-derived UTF-8 source anchors were compared with the extracted content of `persian_test.pdf` on Windows using the repository's `DocumentExtractionService`. Result: **4 EXACT** (01, 06, 07, 10); **5 WHITESPACE_OR_ZWNJ** (03, 04, 05, 08, 09); **1 NEEDS_CONTENT_REVIEW** (02). The parser again emitted the non-fatal `Xref table not zero-indexed` warning and completed.
- **Interpretation:** 9/10 anchors are present under either exact substring equality or a combined whitespace/ZWNJ-insensitive substring test; this is **not a 90% semantic extraction recall claim**. The other anchor remains unclassified and may reflect font glyph mapping, RTL order, punctuation, normalization, actual omission or another encoding difference. No full-document fidelity or summary quality conclusion follows from these ten phrases.
- **Next:** inspect only anchor 02 against the local extracted PDF without logging or committing private document text. Distinguish character/codepoint corruption from genuine missing prose; if a parser defect is established, add a minimal synthetic regression and a targeted change. Independent Stage 10 semantic review, representative distinct documents, production quality gates, and holdout evaluation remain outstanding.


### Stage 10: PDF anchor 02 isolated to an embedded punctuation/diacritic mismatch (2026-11-02)

- **Status:** Stage 10 In Progress / Quality Blocked. Documentation-only diagnostic record; Production extractors, summarization and benchmark acceptance rules are unchanged.
- **User's local targeted evidence:** TXT anchor 02 begins `این سند یک متن آزمایشی کاملاً فارسی است`; corresponding near-match from `DocumentExtractionService().extract(persian_test.pdf)` contains `اینسندیکمتنآزمایشیکاملا&فارسیاست` after removing whitespace/ZWNJ. Longest contiguous matching span **25 of 49 codepoints**, and `SequenceMatcher` candidate similarity **0.98** for this anchored substring.
- **Interpretation:** PDF has a highly similar local sentence, with the visible Arabic fathatan mark on `کاملاً` (`U+064B`) apparently represented as ASCII `&` in `کاملا&`. The original Unicode codepoint mapping and raw pre-RTL `pypdf` output have **not** yet been independently checked; treat character substitution as strongly indicated, not a proven exact decoder/font root cause. One-character disagreement explains why the literal benchmark marks the entire anchor absent. The prior 4/10 exact and 9/10 whitespace/ZWNJ-insensitive rates do **not** measure overall semantic recall.
- **Decision:** Do not globally replace `&`, strip meaningful diacritics from production extraction, or modify the model to make one test PDF pass. Next verify `U+064B` versus `U+0026` in raw `pypdf` page-level `layout` output and examine PDF's embedded font `ToUnicode` map if permitted. If a generalizable defect is confirmed, use a synthetic regression PDF and an isolated parser correction; otherwise document this as source-PDF glyph encoding variability. No model inference, new benchmark or automated regression suite was run for this documentation update; previous **402 passed / 2 warnings** remains the authoritative Windows regression baseline. Holdouts untouched.


### Stage 10: raw pypdf versus RTL-repaired glyph count verified on Windows (2026-11-02)

- **Stage/status:** 10 In Progress / Quality Blocked; no Production rollout, model, extractor or acceptance-gate changes. Local user test used `persian_test.pdf` with `PdfReader(strict=True)` and the same layout extraction mode as the actual service.
- **Observed count before RTL repair:** `U+0026` ampersand **4**, `U+064B` Arabic fathatan **0**.
- **Observed count after `DocumentExtractionService._restore_visual_rtl_text`:** ampersand **4**, fathatan **0**. `pypdf` emitted a nonfatal `Xref table not zero-indexed` repair warning, then exited successfully.
- **Diagnosis supported by data:** The four ampersands already occur in raw **layout-mode pypdf Unicode extraction**, before this application's RTL-repair step. Therefore the RTL-repair step did not create these ampersands, and no fathatan characters were present in that pre-repair output. Anchor 02's source `کاملاً` versus near-matching PDF `کاملا&` is consistent with a glyph/character mapping issue upstream of RTL repair, but the evidence does **not** isolate the PDF generator, embedded font `ToUnicode` CMap, or pypdf decoder. Counts of four ampersands do not prove every occurrence corresponds to a diacritic.
- **Next read-only diagnosis:** Compare pypdf `plain` versus `layout` mode Unicode counts on the same local PDF, optionally inspect font `/ToUnicode` presence. Avoid globally replacing `&`, stripping diacritics or changing Production extraction to fit one PDF. If a general defect is proven, create a minimal synthetic PDF regression test before a targeted code change.
- **Verification/constraints:** No new pytest or real model inference run on this documentation update; last confirmed full Windows regression on prior code commit was **402 Passed, 0 Failed, 2 deprecation warnings**. Independent semantic quality review, distinct authentic documents and held-out evaluation remain outstanding; Stage 10 **not completed**.


### Stage 10: pypdf plain and layout mode parity confirmed (2026-11-02)

- **Stage/status:** Stage 10 In Progress / Quality Blocked (NO-GO). User ran a read-only diagnostic on their local two-page Persian text PDF. No application source or PDF file content added to the repository.
- **Page 1:** `pypdf.PdfReader(strict=True)` page extraction in both `plain` and `layout` reported `U+0026` ampersand = **3**, `U+064B` Arabic fathatan = **0**. The page has **3 fonts**, each reporting `/ToUnicode` present.
- **Page 2:** Both extraction modes reported ampersand = **1**, fathatan = **0**. Again **3 fonts** reported `/ToUnicode` present. Totals across both pages: **4 ampersands, zero fathatan** per mode. The known non-fatal `Xref table not zero-indexed` warning was emitted.
- **Inference:** Switching modes `layout` → `plain` does not recover fathatan or eliminate ampersands in this input. Existing `/ToUnicode` CMaps do not establish correct individual mappings. The origin of the `کاملا&` near-match for source `کاملاً` is upstream of the application's RTL repair and shared by both pypdf extraction modes, but the particular responsible producer/font/CMap/decoder cannot be proven from these counts alone. Four `&` characters should not all be assumed to represent diacritics.
- **Decision / next:** Treat this as a document-specific glyph-mapping limitation pending source-PDF/CMap confirmation. No global `&` substitution, parser change, dependency upgrade, new default mode, or mT5 change is justified solely by this example. Prioritize independent semantic review, more *distinct* authorized Persian documents, and held-out quality gates before marking Stage 10 complete; if a general reproducible decoder defect is found, capture a synthetic failing PDF fixture and make a minimal tested change.
- **Verification:** Latest full Windows suite reported **402 Passed, 0 Failed, 2 deprecation warnings** on application code unchanged since that test; **no additional pytest** performed for this documentation-only update. Commit to `main` records new evidence only.


### Stage 10: source-grounded semantic quality audit and distinct-document evaluation plan (2026-11-02)

- **Stage/status:** Stage 10 In Progress / Quality Blocked (Production NO-GO). A new review report was added: `docs/STAGE10_QUALITY_REVIEW_2026-11-02.md`. No source, model, config, API, dependencies, benchmark dataset or holdout changes.
- **Fresh direct source audit:** original authorized `persian_test.txt` and `persian_test.docx` loaded; TXT stripped 3,069 chars, DOCX nonempty paragraphs 3,055 chars; exact equality after Unicode whitespace collapse (3,055 chars). Twelve selected source anchors for hypothetical scope, explicit fictional disclaimer, 3 district trends, negative causation, uncertainty, quoted leak confirmation warning, conditional frequency, frequency caveat, fictional examples and Persian digits appeared **12/12 in both**. This is source format fidelity only, **not summarization accuracy**. The PDF was *not* reprocessed in this source audit; prior user-side extraction observations are cited separately.
- **Review of actual previously recorded outputs:** frozen five-case synthetic Development v4 mT5 medium assistant assessment 3/19 covered, 2 critical direction distortions, 0/5 short/long distinction; v5 source-only extractive assistant assessment 4/19 short, 11/19 medium, 18/19 long, 0 assistant-labeled distortions, 49 assistant-segmented claims with 0 labeled unsupported, 5/5 short-vs-long. These are **historical provisional observations**, not fresh scoring or independent reviewer validation. Raw v5 result/review files were not available for fresh claim-level checking in this turn. Holdouts sealed.
- **Semantic safety finding:** the sample's fictional-scenario qualifier is a separate sentence preceding district-specific change claims; the code enumerates/ranks sentences individually, so quoting an isolated trend can lose the hypothetical scope. This is an architectural/source-context **risk**, not proof a specific generated summary failed. The prohibited quoted wording `نشتی ... تأیید شد` and source `الزاماً ... نیست` likewise demand contextual human review.
- **Tests/results:** direct TXT/DOCX equality and anchor checks executed in this assessment; no real mT5 generation, no new pytest, no peak RAM or controlled latency measurements performed here. Last user-confirmed Windows engineering suite remains **402 passed, 0 failed, 2 warnings** on unchanged application code.
- **Next-stage readiness / blocker:** report provides exact existing Windows CLI for paired default mT5 versus opt-in v5 experiments on **two distinct repository Development Markdown documents**, all three lengths, plus unreviewed review templates. Independent human fact/atomic-claim adjudication and more genuinely distinct authorized Persian field documents are required before Stage 10 GO. No Production or Stage 11 promotion.


### Stage 10: fixed real-project dataset manifest drift detected during quality audit (2026-11-02)

- **Issue:** GitHub check at commit `68a5f150b1661f43400d70bef9d5ce53180d193f` confirms the pinned manifest `benchmarks/fixtures/real_project_documents_v1.json` expects holdout source SHA `70cc29fc8b134a478365ba9a5badc1a88330c584` but current `docs/POST_MVP_DEVELOPMENT_PLAN.md` blob is `0d6ec8df2b9a1e3d24c924fbaf1c5c8fff2ee5bb`. `project_document_dataset.prepare` verifies **all** manifest entries before `quality_benchmark --split dev` can run; re-preparing now will fail even though no holdout summary is requested.
- **Safe response:** No holdout read/evaluation, no manifest rewrite, no bypass of SHA safeguards. Updated `docs/STAGE10_QUALITY_REVIEW_2026-11-02.md` commands to use the pre-existing `local_quality_project_v1.json` (previously verified SHA-256 `fbc292ba36d07581614810efad42f0585ca9a50605e70a966048c33b9ac63e3c`), checked on the user's machine before any `run --split dev`. Without that file, authentic-document rerun remains blocked until a separately designed dev-only dataset protocol is agreed.
- **Status:** Stage 10 In Progress / Quality Blocked (NO-GO). Documentation correction only; no new tests or model inference.


### Stage 10: Windows pinned authentic Development two-path raw runs completed (2026-11-02)

- **Stage/status:** Stage 10 **In Progress / Quality Blocked (Production NO-GO)**. New user-side Windows runtime evidence from the fixed, previously prepared real-project dataset; this report records the CLI outcome only, not independently evaluated semantic quality.
- **Dataset integrity:** The user verified that `local_quality_project_v1.json` exists and that its SHA-256 equals the previously frozen `fbc292ba36d07581614810efad42f0585ca9a50605e70a966048c33b9ac63e3c`. No dataset regeneration or manifest/holdout edits. Both commands used `--split dev --lengths short medium long`, i.e. two distinct development project source documents and the three requested output tiers; the holdout remains sealed.
- **Baseline command outcome:** `python -m benchmarks.quality_benchmark --dataset $dataset run --split dev --lengths short medium long --output local_stage10_project_default_v2.json` printed `Saved raw model outputs: local_stage10_project_default_v2.json` without a reported exception.
- **Extractive v5 command outcome:** the corresponding `run --split dev --lengths short medium long --preserve-map-evidence --source-grounded-final --balanced-source-final --source-sentence-final --output local_stage10_project_extract_v5_v2.json` printed `Saved raw model outputs: local_stage10_project_extract_v5_v2.json` without a reported exception. The v5 flag is source-only (no mT5 `generate`); it is not a generative model improvement.
- **Warnings:** both commands emitted Transformers' standard `T5Tokenizer` legacy behavior notification. No errors in the supplied logs; do not change tokenizer legacy semantics mid-pair.
- **What is **not** verified:** neither raw JSON file nor run metadata/summaries has been furnished to this reviewer. The logged CLI completion does **not** prove all per-case results were successful, that source facts were covered, that short/medium/long differ, that negation/hypothetical scope was preserved, or that latency/RAM/unsupported claims met gates. No new `pytest` or controlled performance test in this turn. The last actual user-confirmed full suite remains **402 passed, 0 failed, 2 warnings** on unchanged source.
- **Next:** use the existing `benchmarks.stage10_compare` tool on the exact fixed dataset and these two raw runs; produce separate `benchmarks.quality_benchmark review-template` artifacts. Upload/review both raw run JSONs (or sanitize locally as needed) to adjudicate factual coverage, polarity, conditional/quoted scope, and short/medium/long. Do not run `score` on unreviewed templates or label an assistant draft independent human review. Keep local JSON outputs out of GitHub and leave all holdouts sealed. No API, model, parser, benchmark schema or dependency changes warranted by completion logs alone.


### Stage 10: Actual paired project Development review and numbered-list selector fix (2026-11-02)

- **Status:** In Progress / Quality Blocked (Production NO-GO). User uploaded an authentic fixed-dataset six-pair raw comparison and candidate v5 run. Detailed assistant-only review: docs/STAGE10_PROJECT_DEV_V2_REVIEW.md.
- **Provenance:** Dataset SHA-256 fbc292ba36d07581614810efad42f0585ca9a50605e70a966048c33b9ac63e3c; candidate canonical run SHA-256 ac4fa5ce8b182c0ee43a9e49fd2c667deb5868517908e70ec6e2826201b96a84 agrees with comparator. The original default mT5 run JSON was not uploaded; comparator contains only baseline metadata. No holdout access.
- **Observed results:** 6/6 paired outputs succeeded and changed across baseline/candidate; v5 tier tokens architecture 33/74/118 and MVP plan 31/80/119 (limits 40/80/120), with no repeated four-grams. Assistant provisional v5 fact coverage: short 1/6, medium 1/6, long 2/6, below frozen real-development medium >=3/6 gate; independent human semantic reviews not performed.
- **Defect and change:** The pre-fix v5 MVP medium/long summaries contain orphan Markdown fragment **کارها:** 1. from a long numbered-list item's numeric prefix. Added _ORDERED_BULLET recognition only to the experimental source-sentence candidate parser, preserving the existing short numbered PDF heading branch; added targeted fake-provider test. Model defaults, config, DI, API, benchmark fixtures, privacy boundaries and dependencies unchanged.
- **Verification:** Source identity/JSON hash and isolated numbered-item matching preflight verified; actual full pytest and new candidate re-run NOT executed here. Last user-confirmed engineering full suite was 402 passed / 2 warnings on previous code. User must test changed code after pull and use new candidate output filename, then complete independent semantic review. No Stage 10 completion.
- **Changed files:** source sentence v5 service, v5 regression tests, progress record, new detailed review report. **Commit SHA:** retrieve from the Git commit containing this entry.

### Stage 10: post-fix v5 v3 verified on Windows (2026-11-03)

- **Status:** Stage 10 In Progress / Quality Blocked (Production NO-GO). Detailed v3 supplement: docs/STAGE10_PROJECT_DEV_V2_REVIEW.md.
- **Changed files for this documentation update:** docs/STAGE10_PROJECT_DEV_V2_REVIEW.md; docs/IMPLEMENTATION_PROGRESS.md. No new application source/model/config/tests changes in this update.
- **User-run test verification at source commit 184b6ac44346bf08e073e4a27f704bd24c38e759:** pip check passed; compileall passed; focused tests **60 passed / 4.73s**; full suite **403 passed / 12.64s**, **2 nonblocking dependency deprecation warnings**.
- **User-run fixed-dataset development rerun:** six v5 source_sentence_only_no_model_generate successes, all three tiers for each of two distinct engineering Markdown sources, fixed SHA-256 fbc292ba36d07581614810efad42f0585ca9a50605e70a966048c33b9ac63e3c; uploaded v3 run canonical hash f4f3795213bfcb45cfc3da40fcaebc61aedfb614d0375f32395a9c03084e8537. User comparison CLI reported paired=6 changed=6 versus original default v2 but the v3 comparison JSON itself was not supplied.
- **Before/after exact effect:** architecture 3/3 tier outputs unchanged; MVP short unchanged; MVP medium and long each lost only malformed Markdown segment **کارها:** 1. and reduced 80->74 and 119->113 encoded tokens. No output errors and all six within ceilings 40/80/120.
- **Semantic limitation:** assistant-judged required fact coverage **still 1/6 medium**, below frozen >=3/6 real-project Development criterion; short 1/6, long 2/6. Semicolon-terminated clauses and missing adjacent qualifications remain a qualitative risk. No independent human claim review, fresh default-v2 raw summaries, distinct external documents or controlled peak RAM measurement. No holdout usage; source-only v5 is NOT a generative mT5 quality improvement.
- **Next:** independent fact and atomic-claim assessment, inspect default-v2 raw run JSON, and diagnose missing key facts before deciding any further targeted change. Production NO-GO. This documentation-only update does not rerun tests in the assistant environment.

### Stage 10: actual baseline-v2 raw outputs and v3 comparator reviewed (2026-11-03)

- **Stage/status:** 10, **In Progress / Quality Blocked (Production NO-GO)**. Report: `docs/STAGE10_PROJECT_DEV_V2_REVIEW.md`; documentation-only review update.
- **Artifacts verified:** User-provided full `local_stage10_project_default_v2.json` and `local_stage10_project_compare_default_v5_v3.json`, joined with previously uploaded full `local_stage10_project_extract_v5_v3.json`. All three agree on fixed dataset SHA-256 `fbc292ba36d07581614810efad42f0585ca9a50605e70a966048c33b9ac63e3c`; canonical baseline run SHA `e4846212186d4fea7afd21b39ffb851328350dd145688480bb56c7555b597b86` and candidate run SHA `f4f3795213bfcb45cfc3da40fcaebc61aedfb614d0375f32395a9c03084e8537` exactly match comparator's two recorded run hashes.
- **Fact findings (assistant-only, not independent review):** On two authentic engineering Markdown Development documents, six fixed unique reference facts and three tiers: default mT5 covered **0/6 short, 0/6 medium, 0/6 long**; v5 source-extractive covered **1/6 short, 1/6 medium, 2/6 long**. Both below frozen real-project medium **>=3/6** threshold. The default architecture summary was exactly identical across all three tiers; default MVP medium and long were identical. v5 produced 3 distinct tiers for both documents. All 12 outputs successful and within `40/80/120` encoded-token ceilings; no repeated four-grams in comparator.
- **Specific qualitative defects:** Default MVP short contains a truncated second clause, and medium/long contain a grammatically awkward, possibly unsupported agent/action paraphrase about the Repository checking rules. v5 v3 eliminated the prior `**کارها:** 1.` fragment, but its MVP long and architecture medium excerpts still omit semicolon-following qualifications. All claims still need reviewer-adjudicated evidence, particularly contextual negation and hypothetical scope. This was not an mT5-model improvement: `source_sentence_only_no_model_generate`.
- **Verification:** Python JSON SHA and paired-data/ceiling checks executed in assistant runtime; original source snippets inspected. **No new model inference or pytest** for this documentation-only update; last Windows suite **403 passed**, **2 warnings**, focused **60 passed**. No peak-RAM/controlled-latency benchmark and no holdout access. Unsupported-claim rate **NOT SCORED** (not zero).
- **Changes:** `docs/STAGE10_PROJECT_DEV_V2_REVIEW.md` and `docs/IMPLEMENTATION_PROGRESS.md` only. No source, dependencies, config, model, frozen dataset, or API changes. **Commit SHA:** see GitHub commit containing this update.
- **Next:** Human independent fact and atomic-claim review (use existing v3 review-template, not stale v2 template); collect distinct authorized Persian field documents and evaluate negation, conditionality, quotations, numbers and completeness before considering targeted changes. Production **NO-GO**.

### Stage 10: assistant-proposed v5 v3 review template prepared (2026-11-03)

- **Status:** In Progress / Quality Blocked (Production NO-GO), no new source, test, config, model or API changes; report supplemented in `docs/STAGE10_PROJECT_DEV_V2_REVIEW.md`.
- **Input integrity:** User-uploaded blank v3 review template has 6 results × 3 fact labels (all null), no claims, and run hash `f4f3795213bfcb45cfc3da40fcaebc61aedfb614d0375f32395a9c03084e8537` matching the actual uploaded v3 candidate; fixed Development dataset hash `fbc292ba36d07581614810efad42f0585ca9a50605e70a966048c33b9ac63e3c`.
- **Local deliverables (not committed, preserving user/holdout privacy):** `local_stage10_project_extract_review_v3_assistant_draft.json` with assistant fact labels and 22 segmented atomic claims/evidence, plus separate `STAGE10_V5_V3_ASSISTANT_REVIEW_NOTES.md`. All evidence source quotes are exact substrings of the source documents; all six source/tier case keys match. Assistant-provisional 4/18 covered, 14/18 omitted, 0/18 distorted; short 1/6, medium 1/6, long 2/6; 22/22 claims assistant-marked supported; **no independent human semantic validation**.
- **Assessment:** Frozen medium authentic Development gate `>=3/6` still fails, and source sentences can lose same-line continuation/qualifiers. No new model or pytest tests run; prior Windows code test remains **403 passed, 2 warnings**. No official `quality_benchmark score` run or human-signoff. Human must validate the assistant draft rather than just rename it; holdouts sealed.
- **Next:** Independent fact/atomic-claim review, then `score` only with source-checked labels and matching local dataset; further varied Persian documents required. Production NO-GO.
