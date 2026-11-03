# Stage 13 — Quality Evaluation, Hardening & Final Delivery

**Date:** 2026-11-03  
**Status:** **In Progress — Windows/Docker/E2E verification and semantic review pending**  
**Scope:** Source-grounded Document Query and legacy general summarization as *independent* functions. No model fine-tuning, new data source, holdout access, OCR, authentication or new production dependency.

## Baseline and frozen quality decisions

- Stage 9: fixed benchmark in `benchmarks/fixtures/quality_v1.json`; its **holdout remains sealed**. Do not modify it or tune on it. Run default/candidate comparisons on Development only.
- Stage 10: the user accepted existing quality for continuing development. **This is not a passed semantic Production gate.** The documented v6 source-only trial preserved **2/6 frozen Development facts for medium** versus its pre-agreed **>=3/6** acceptance threshold. Human-independent semantic review, hallucination scoring and Production GO are still unavailable. The previously logged raw default/v5/v6 comparisons must not be presented as new model measurements or factual improvement.
- Stage 11: actual user-run Windows Development retrieval Benchmark had **Recall@1=1.000, Recall@3=1.000 on 15 labeled synthetic Development questions** (source-quote recall, not answer correctness).
- Stage 12: user-run Windows results at commit `5ca2d840f96637c547509b600e63f3104128842b`: **31 Stage 12 tests passed, 460 full-suite tests passed, 2 third-party warnings**; a live request at `127.0.0.1:8001` returned verbatim `۱۴ آبان ۱۴۰۵` and true `paragraph=1`, `page=null`. This verified one TXT answer, not a representative quality distribution or a PDF/DOCX acceptance audit.

## Reproducible Stage 13 Development-only quality benchmark

New `benchmarks/fixtures/stage13_query_dev_v1.json` contains seven small, synthetic, CC0-labeled **Development** TXT documents and **11** independent test questions/labels:
- explicit date, named responsible person and number answers; labels require **exact full source excerpts**;
- a genuinely missing topic and a lexically similar question with **no explicit amount**;
- competing date, responsible-person, and budget values; no guessed resolution;
- short and long topic-focused summaries with expected/excluded original quotes;
- an untrusted-source instruction line with a private canary; an unrelated answer must not follow or include that line.

New `benchmarks/stage13_quality_benchmark.py` runs the actual (non-generative) `DocumentQueryService`, plus the existing, unchanged Stage 11 Development retrieval benchmark. It validates fixture IDs, bounds, source anchoring and Development split before execution; no holdout data are evaluated or modified. Its result is **new, no-overwrite JSON** recording source and label SHA-256, per-case status/support/latency (without private raw text), denominators and:

| Metric | Exact computation | Limitation |
| --- | --- | --- |
| `Recall@1` / `Recall@3` | Existing 15-label Stage 11 Development exact-quote recall | Not semantic recall |
| `Answer Exact Match` | Count of correct verbatim **full source excerpt** among labeled `found/answer` cases | Not fact-entailment outside the excerpt |
| `Evidence Support Rate` | Returned evidence spans exactly present in source and in the parser-indicated TXT paragraph / all returned evidence spans | Can still contain misleading surrounding context |
| `No-answer Accuracy` | Expected `not_found` cases with null answer and no evidence / expected `not_found` cases | Small synthetic negative set |
| `Ambiguous Detection` | Expected ambiguous cases with null answer and all labeled competing spans / expected ambiguous cases | Not a comprehensive contradiction detector |
| `Focused Coverage` | Expected on-topic quotes present, off-topic quotes absent, all output source-cited, under length budget / focused cases | Character budgets, not semantic summary quality |
| `Status Accuracy` | Expected status == actual status / 11 labels | Label/fixture-dependent |
| `Latency` | Per-query local `perf_counter` timings; median and nearest-rank p95 | Small sample, environment dependent, no throughput guarantee |
| `Python allocation peak` | `tracemalloc` peak during query loop (Python allocator only) | **Not native memory or peak RSS** |

**Important:** All metric values after Stage 13 changes are **Not Run until the user's Windows execution**. Do not infer numerical success from the fixture's expected labels; the benchmark and tests are designed to expose failures. OS peak RSS is reported as `NOT_MEASURED`, model-memory figures are not invented, and frozen Stage 10 human semantic GO is `NOT_RETESTED`.

Run from the repository root (Windows PowerShell):

```powershell
git pull --ff-only origin main
$env:env_type = "development"
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m compileall -q src benchmarks tests
.\.venv\Scripts\python.exe -m pytest -q tests/test_stage13_quality.py tests/test_stage12_document_query.py tests/test_stage11_retrieval.py tests/test_stage7_hardening.py
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m benchmarks.stage13_quality_benchmark --output ".\local_stage13_query_dev_metrics_v1.json"
Get-Content -LiteralPath ".\local_stage13_query_dev_metrics_v1.json" -Raw
```

Outputs containing sensitive local material should not be committed; if the JSON output exists, choose a new path (the exporter refuses overwrite).

## Stage 9 / Stage 10 general summarization comparison

General mT5 summarization is not the new source-only Document Query benchmark. The following separate commands reproduce existing **Development-only** baseline and candidate models on user hardware, with weights when available:

```powershell
.\.venv\Scripts\python.exe -m benchmarks.quality_benchmark validate
.\.venv\Scripts\python.exe -m benchmarks.quality_benchmark run --split dev --output ".\local_quality_stage13_default_dev.json"
# For an opt-in candidate with previously documented flags, first review its Stage 10 CLI help and recorded experiment configuration.
# Compare existing compatible Development runs without rewriting/faking their model settings:
# .\.venv\Scripts\python.exe -m benchmarks.stage10_compare --dataset benchmarks/fixtures/quality_v1.json --baseline PATH_TO_BASELINE.json --candidate PATH_TO_CANDIDATE.json --output ".\local_stage13_model_compare.json"
```

If no compatible baseline/candidate raw runs are available, comparison is **NOT RUN**, not zero improvement. Human fact-coverage annotation and stage-specific quality acceptance must use the original frozen labels and review instructions in `docs/STAGE9_QUALITY_BASELINE.md` and Stage 10 review reports; the exact claims are not inferred from length/repetition or a 200 response. **No new Stage 10 performance is claimed in Stage 13.**

## HTTP E2E and safety checks

- New `tests/e2e_document_query_smoke.py` extends the existing Stage 8 live HTTP testing approach using already-implemented synthetic TXT/PDF (with ToUnicode text layer)/DOCX generators from `tests/e2e_http_smoke.py`. It exercises **both query modes in all three formats** against a running server, checks the original source text, preserves PDF page or TXT/DOCX paragraph references, verifies `not_found` and ambiguous two-date requests, validates corrupted PDF redaction and duplicate multipart-field 422. It checks that all three legacy Summarization paths still appear in OpenAPI, **without loading mT5**.
- New `tests/test_stage13_quality.py` covers deterministic metric and provenance contracts, fixture validation/fail-closed negative cases, non-overwriting report exports, real-app HTTP source-grounded TXT, DOCX topic filtering, source-text instruction isolation, no-result behavior, invalid PDF redaction, asynchronous offloading and Task cancellation.
- The existing `UploadBodyLimitMiddleware` enforces multipart-only admission, 20 MiB/file validation and configured aggregate limits, and has existing Stage 7 hardening tests for concurrent admission, idle timeout and disk-backed bounded spool. **No additional production runtime control was warranted from the confirmed Stage 12 baseline.** Heavy parser work is dispatched with `asyncio.to_thread`; cancellation stops the awaiting task but **does not forcibly terminate the worker thread**. Resource use under stress should be measured independently.

Start Uvicorn (terminal A) and leave it running:

```powershell
$env:env_type = "development"
.\.venv\Scripts\python.exe -m uvicorn src.host.app:app --host 127.0.0.1 --port 8001
```

Run E2E (terminal B):

```powershell
.\.venv\Scripts\python.exe tests/e2e_document_query_smoke.py --base-url http://127.0.0.1:8001
# Optional existing real-model/legacy Summarization E2E, which may download mT5 weights:
# .\.venv\Scripts\python.exe tests/e2e_http_smoke.py --base-url http://127.0.0.1:8001
```

Never regard document contents as instructions; the service returns source-only snippets and does not pass source instructions to an LLM in the query path. Quoting a malicious passage on an explicit matching query is still possible; source review remains the user's responsibility. No new query-log ingestion or persistence was added.

## Docker, README and release safety

- `README.md` explicitly distinguishes the **legacy published** `ghcr.io/amirmahdimtz/mt5-persian-summary:stage8` image (MVP) from current Stage 13 source code. It documents Document Query and both modes, source citations, constraints, Windows/Python tests and a **local preview** Docker image tagged `mt5-persian-summary:stage13-dev`.
- `compose.yaml` now uses the local source-build label `stage13-dev`, preventing the previous `stage8` local tag from being overwritten when building current source. Same port/memory/CPU/security/volume and model download policies.
- Manual-only `.github/workflows/docker-image.yml` now publishes (if explicitly dispatched on main) to `:stage13-dev` rather than overwriting the old `:stage8` tag, checks all four OpenAPI routes and a synthetic source-cited Document Query HTTP response **before** pushing. **No workflow was dispatched, no Docker image was built, and no GHCR artifact was published by this work.** Publishing a Development preview is not Production GO.
- No changes to `Dockerfile`, model provider, default summarization API, model/license/revision, Stage 9/10 frozen fixtures, Stage 11 retrieval algorithm, or production dependency versions.

## Verification and known gaps

| Verification | Present evidence |
| --- | --- |
| Latest pre-Stage-13 Windows full regression | 460 passed, 2 third-party warnings (Stage 12) |
| Stage 13 benchmark on full Repository | **NOT RUN** |
| Stage 13 new pytest + full suite | **NOT RUN on user Windows** |
| Standalone live TXT/PDF/DOCX query E2E | **NOT RUN** |
| Existing live model Summarization E2E | **NOT RUN in Stage 13** |
| Docker source build, manual workflow, GHCR publish | **NOT RUN** |
| OS peak RSS under realistic concurrency | **NOT MEASURED** |
| Human-evaluated Stage 10 semantic quality gate | **UNMET / Production NO-GO** |

**Acceptance remains blocked** until real Windows stage tests, Development metrics, live E2E and Docker source build (or explicit recorded inability) are reviewed; semantic quality requires distinct acceptance before any Production rollout. After the user's test results, update `docs/IMPLEMENTATION_PROGRESS.md`, record actual metrics, failures and SHA, and only mark Stage 13 Completed for the exact verified scope. Backlog: diverse real authorized Persian PDFs/DOCX and OCR outside scope, deeper semantic/evidence entailment checks, OS RSS and load/timeout benchmarking, Stage 10 quality improvement and eventual independent Production signoff.

## Windows Development quality and live HTTP verification (2026-11-03)

**Recorded verification state: Stage 13 Development evaluation for Document Query PASSED; Stage 13 overall remains In Progress, Production semantic GO NOT APPROVED.** This section updates earlier "NOT RUN" entries, which are preserved above as the timeline before user execution.

### User Windows environment and regression

- Fast-forward pull to implementation SHA `8ef942769f59c83239363888e9251eb60242e3ae` confirmed.
- Python dependencies reported satisfied, `pip check` had no broken requirements, and `compileall -q src benchmarks tests` returned without errors.
- `pytest -q tests/test_stage13_quality.py tests/test_stage12_document_query.py tests/test_stage11_retrieval.py tests/test_stage7_hardening.py`: **87 passed, 1 warning, 0 failed in 4.50s**.
- `pytest -q`: **478 passed, 2 warnings, 0 failed in 14.82s**. Warnings from third-party Starlette/TestClient and httpx deprecated API use were nonblocking; no assertion or setup failures.

### Measured, reproducible synthetic Development-only quality

User ran `python -m benchmarks.stage13_quality_benchmark --output local_stage13_query_dev_metrics_v1.json` and pasted the full JSON.

| Metric | Observed result | Denominator / interpretation |
| --- | --- | --- |
| Stage 11 Recall@1, Recall@3 | **1.000, 1.000** | 15 fixed Development retrieval queries |
| Stage 13 status accuracy | **1.000** | 11 synthetic labeled Document Query scenarios |
| Answer exact match | **1.000** | 4 exact source-excerpt answer cases |
| Evidence support rate | **1.000** | 14 evidence excerpts present at parser-established TXT paragraph |
| No-answer accuracy | **1.000** | 2 negative queries |
| Ambiguous detection | **1.000** | 3 competing date/person/amount cases |
| Focused coverage | **1.000** | 2 topic-focused cases |
| Median query latency | **4.611 ms** | 11 local calls; not server/transport latency |
| P95 query latency (nearest rank) | **26.881 ms** | 11 local calls; not statistically representative |
| Python-tracked allocation peak | **251,140 bytes** | `tracemalloc` only; not process RSS or PyTorch native memory |
| Peak process RSS | **NOT_MEASURED** | No memory-profile measurement |
| Stage 10 frozen semantic gate | **NOT_RETESTED** | Previously unmet |
| Production semantic quality gate | **NOT_APPROVED** | Not inferred from exact-match score |

Reported provenance: `query_fixture_sha256=e169b6d2e3f4196c05c93a5c80dcf617af14438922a206ef03d4ce4e3a88824c`; `stage9_dev_dataset_sha256=cc907d6b16a4b68685b280002bb0a0f550ce6ce3966941c8732702c016f8a9a9`; `stage11_dev_labels_sha256=7fa910edc47c98f712d0f9f83eb646998f7eb859c4a4d2e42153ad524c6e770e`. The 11 status predictions all matched their expected labels. The original Stage 9/10 Holdout was not used.

**Evaluation validity:** These metrics verify an extractive baseline against small synthetic Development labels, not independent semantic entailment or generalization. A quoted source sentence may still be misleading if its subject, negation or context was misidentified. Do not claim that the general-purpose mT5 summary quality improved.

### Live HTTP End-to-End across supported formats

User ran `python tests/e2e_document_query_smoke.py --base-url http://127.0.0.1:8001` against a running Uvicorn application:

| Document | `answer` request | `focused_summary` request |
| --- | ---: | ---: |
| TXT | **PASS, 11.1 ms** | **PASS, 11.3 ms** |
| PDF with text layer | **PASS, 12.0 ms** | **PASS, 11.8 ms** |
| DOCX | **PASS, 52.1 ms** | **PASS, 47.7 ms** |

- **6/6** document/mode combinations passed; the script required verbatim evidence and correct actual page/paragraph location.
- Also passed: `not_found` abstention without invented answer, `ambiguous` without invented resolution, malformed-PDF redaction (HTTP 422) and repeated multipart query (HTTP 422).
- Health and OpenAPI requests returned HTTP 200; the script checked the three legacy Summarization operation registrations and the new Document Query operation. Server logs showed HTTP 200 for successful requests and HTTP 422 for expected validation failures.
- Reported HTTP **median request duration 11.93 ms** across 6 small requests. It is not load-test throughput or a latency service-level objective. Server peak RSS **NOT_MEASURED**. The test calls the extractive route, not the mT5 generative path.

### Open gates and handoff

**Done for Development:** Stage 13 Python/regression tests, new quality benchmark with hashes and scores, live request validation for three source formats and both Document Query modes, syntactic/safe-error and non-blocking regression coverage.

**Still NOT RUN:** Local current-source Docker build/health/Document Query E2E (or equivalent manually triggered CI workflow); optional real-mT5 summarization E2E; new Stage 9 baseline-versus-Stage 10 candidate model quality comparison. **Still NOT MEASURED:** peak native/process RSS, realistic concurrent workload and independent semantic factual agreement on varied authorized Persian documents. Stage 10 Production gate remains unmet and explicitly deferred.

**Next immediate reproducible Docker preview on the user's system:**

```powershell
git pull --ff-only origin main
docker build -t mt5-persian-summary:stage13-dev .
docker volume create mt5_hf_cache
docker run -d --name mt5-stage13-preview --init --memory 8g --cpus 2 --pids-limit 256 --security-opt no-new-privileges -p 127.0.0.1:8003:8000 -v mt5_hf_cache:/home/app/.cache/huggingface -e env_type=production mt5-persian-summary:stage13-dev
curl.exe -sS http://127.0.0.1:8003/api/v1/health
.\.venv\Scripts\python.exe tests/e2e_document_query_smoke.py --base-url http://127.0.0.1:8003
```

If Docker is unavailable, report that explicitly rather than claiming delivery verification. The `:stage8` image must not be substituted for current-source Stage 13 preview. No images or releases were published as part of this documentation update.

**Final Stage 13 status: In Progress**, pending the remaining delivery and quality scopes. No production application code, tests, frozen fixture or benchmark logic changed by recording these results.
