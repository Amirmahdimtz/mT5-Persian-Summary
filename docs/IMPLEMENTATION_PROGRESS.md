# Implementation Progress — mT5 Persian Summarization Service

## Stage Overview

| Stage | Status |
| --- | --- |
| 1. Project Setup, DI & FastAPI | Completed |
| 2. mT5 Model Integration | Blocked (real smoke pending) |
| 3. Document Extraction | Not Started |
| 4. Chunking & Long Text Summarization | Not Started |
| 5. Main SummarizationService | Not Started |
| 6. REST API & Upload Validation | Not Started |
| 7. Testing, Security & Optimization | Not Started |
| 8. Docker & Final Delivery | Not Started |

- Last completed stage: **1**
- Active stage: **2 (Blocked: real inference verification pending)**
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

- **Status: Blocked for acceptance verification**. Provider implementation and mocked tests are complete, but real Persian inference was not verified because model dependencies/weights were unavailable. Change Stage 2 to Completed only after an actual Windows CPU smoke test returns a nonempty summary.
- Starting main HEAD: 2466c4812f4a5b0ee4c91f439a46e34c4d389fc0 (verified via GitHub). Branch main had write permission and no active protection.
- Stage 2 changed files: src/infrastructure/ml/mt5_model_provider.py; src/infrastructure/ml/smoke_mt5_model.py; tests/test_mt5_model_provider.py; src/host/res/appsettings.yaml; src/host/res/appsettings.development.yaml; requirements.txt; README.md; docs/STAGE2_MODEL_VERIFICATION.md; docs/IMPLEMENTATION_PROGRESS.md.
- Architecture: existing DI/bootstrap/ConfigReader and health/controller code not changed. New @inject infrastructure provider is singleton per worker; constructor-injected ConfigReader; no model download/import at app startup. Model loaded on first valid summary under a lock. A second lock bounds concurrent inference. Async method uses asyncio.to_thread; synchronous method is CLI-only or to be called on worker threads. Model load errors are cached until restart.
- Model: nafisehNik/mt5-persian-summary at b575560ad967050e77a40f907abb1ebbeefb9a15; model-card MIT license; MT5ForConditionalGeneration / SentencePiece. Main-branch checkpoint is ~1.2 GB pytorch_model.bin, not safetensors; use trust_remote_code=False, weights_only=True. Alternative safetensors model considered; see docs/STAGE2_MODEL_VERIFICATION.md.
- Limits: 1000 input tokens including specials (from model-card example; not confirmed architectural maximum), 20,000 input chars (protective Stage-2 limit), decoder max_length=120. No silent truncation.
- Generation: num_beams=2, repetition_penalty=1.0, length_penalty=2.0, early_stopping=true, do_sample=false. No documented task prefix.
- CPU default, opt-in auto/cuda with validation; memory guidance >=8 GB available for first CPU test (estimate; not measured), use one worker until profiled.
- Dependencies added: transformers>=4.48,<5, torch>=2.6,<3, sentencepiece>=0.2,<0.3. Windows Python 3.12 compatibility is still to be exercised.
- Verification: reconstructed local Python 3.13.5 workspace, python -m compileall -q src tests **Passed**; python -m pytest -q **36 passed, 0 failed** (20 new mocked model tests plus 16 retained Stage-1 regressions). Mock coverage includes DI resolve, singleton, config, validation, token guard, generation/decode, errors, one-time load, concurrency, async method and CPU selection.
- Real-model smoke command python -m src.infrastructure.ml.smoke_mt5_model: **Blocked (attempted, nonzero exit)** because transformers was not installed in sandbox, and external model download unavailable. No weight download, no Persian summary and no real RAM measurements. Windows real inference: **Not Run**.
- Known issues: pickle checkpoint provenance risk; real model generation and Windows/Python 3.12 compatibility unverified; model quality beyond Persian news unassessed; original non-blocking Starlette deprecation warning may remain.
- Next step: run Windows smoke and tests using README instructions. Stage 3 extraction is architecturally independent and can be planned, but Stage 2 acceptance is pending.
- Commit SHA: see repository main HEAD for this Stage-2 integration commit (the commit SHA cannot be stored in its own content without another commit).
