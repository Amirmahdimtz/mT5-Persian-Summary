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
| 7. Testing, Security & Optimization | In Progress |
| 8. Docker & Final Delivery | Not Started |

- Last completed stage: **6**
- Active stage: **7 (awaiting Windows acceptance)**
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
