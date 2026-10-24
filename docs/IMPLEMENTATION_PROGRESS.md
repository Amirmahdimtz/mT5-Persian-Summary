# Implementation Progress — mT5 Persian Summarization Service

## Stage Overview

| Stage | Status |
| --- | --- |
| 1. Project Setup, DI & FastAPI | Completed |
| 2. mT5 Model Integration | Completed |
| 3. Document Extraction | In Progress |
| 4. Chunking & Long Text Summarization | Not Started |
| 5. Main SummarizationService | Not Started |
| 6. REST API & Upload Validation | Not Started |
| 7. Testing, Security & Optimization | Not Started |
| 8. Docker & Final Delivery | Not Started |

- Last completed stage: **2**
- Active stage: **3 (In Progress — target-runtime regression pending)**
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
