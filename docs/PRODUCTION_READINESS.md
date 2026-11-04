# Production Readiness & Quality Signoff

**Date:** 2026-11-03  
**Status:** **In Progress — PRODUCTION NO-GO**. Stage 13 Development delivery remains Completed.

## Evidence and blockers

| Area | Existing evidence | Production status |
| --- | --- | --- |
| Engineering | User Windows full suite: 478 passed, 2 dependency warnings | Development PASS |
| Document Query | 15/15 retrieval, 11/11 synthetic Development statuses, 6 local and 6 Docker HTTP file/mode E2E successes | Development PASS only |
| General mT5 summarization | Frozen Stage 10 real-project medium fact coverage **2/6** versus target **≥3/6** | **FAILED — NO-GO** |
| Model-in-Docker readiness | Stage 13 Docker checks only exercised extractive Document Query; no real model generation | NOT VERIFIED |
| Real-world quality | Stage 9 proposed ~30–50 authorized Persian TXT/PDF-text/DOCX documents, ≥100 independently annotated queries | NOT RUN |
| OS/native memory and load | Only Python tracemalloc and tiny synthetic HTTP timing measurements | NOT MEASURED |
| Security | No native authentication, user quota or rate limiting; local Docker host binds loopback | **Public exposure BLOCKED** |

Model revision remains `b575560ad967050e77a40f907abb1ebbeefb9a15` with `trust_remote_code=False` and `weights_only=True`; the model uses legacy `.bin` weights. Liveness `/api/v1/health` is **not** model readiness. Document Query returns original extractive citations, not generated mT5 outputs.

## A. Dependency snapshot and safe, separate Docker candidate

`constraints/docker-linux-cpu-2026-11.txt` freezes the **48 installed versions** observed in the previous successful Linux/amd64 Python 3.12 Docker build, including `torch==2.15.0+cpu` and `pypdf==6.21.4`. The Dockerfile uses it for the PyTorch and application `pip install` commands, and .dockerignore includes the file. **This modified Dockerfile has NOT been built or validated yet.**

This is **version pinning only**, not wheel-hash verification, immutable base image, SBOM, CVE scan, license audit or a formal supply-chain approval. GitHub's manual-only Docker workflow now makes `publish_preview` an explicit boolean input defaulting to `false`; no workflow was dispatched and no image was published.

From the repository root in Windows PowerShell:

```powershell
git pull --ff-only origin main
$env:env_type = "development"
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m compileall -q src benchmarks tests
.\.venv\Scripts\python.exe -m pytest -q tests/test_production_readiness.py tests/test_stage13_quality.py tests/test_stage8_delivery.py
.\.venv\Scripts\python.exe -m pytest -q
docker build --progress=plain -t mt5-persian-summary:prod-candidate .
docker image inspect mt5-persian-summary:prod-candidate --format '{{.Id}}'
```

**Check** that host port 8004 is available and no existing `mt5-prod-candidate` container is present; do not delete/stop any existing container without separate approval. Build and run under a **new** tag/name to preserve the verified `stage13-dev` preview:

```powershell
docker ps -a --filter "name=mt5-prod-candidate"
Get-NetTCPConnection -State Listen -LocalPort 8004 -ErrorAction SilentlyContinue
docker run -d --name mt5-prod-candidate --init --memory 8g --cpus 2 --pids-limit 256 --security-opt no-new-privileges -p 127.0.0.1:8004:8000 -v mt5_hf_cache:/home/app/.cache/huggingface -e env_type=production mt5-persian-summary:prod-candidate
docker ps --filter "name=mt5-prod-candidate"
curl.exe -sS http://127.0.0.1:8004/api/v1/health
.\.venv\Scripts\python.exe tests/e2e_document_query_smoke.py --base-url http://127.0.0.1:8004
```

This verifies pinned Docker packaging and the extractive feature but **still does not load mT5**.

## B. Opt-in real mT5 Docker inference and resource probe

The following script deliberately invokes `POST /api/v1/summarization/text` with **synthetic Persian input**; it can download the pinned ~1.2 GB model if absent from the mounted cache and requires substantial CPU, RAM and disk. It does not install dependencies, change settings or stop containers. It never writes raw summaries; its local JSON records only output hashes/lengths, HTTP codes, timing, container memory and package version checks.

```powershell
.\.venv\Scripts\python.exe tests/production_model_probe.py --base-url http://127.0.0.1:8004 --container mt5-prod-candidate --parallel 2 --timeout 900 --output ".\local_production_model_probe_v1.json"
Get-Content -LiteralPath ".\local_production_model_probe_v1.json" -Raw
```

The probe exercises first-observed and warm-repeat mT5 inference plus up to two bounded concurrent calls. First-observed may already be warm if the model was loaded earlier. It compares all **48** runtime packages using container `pip freeze --all` and reads Linux cgroup `memory.current`, `memory.peak`, `memory.max` where accessible. Peak is the **container-lifetime high-water mark**, not exclusively the probe's RAM. No throughput SLA, semantic-factual correctness or independent quality approval is inferred.

## C. Fail-closed Production Release Gate

`benchmarks/production_release_gate.py` validates three independent evidence groups: SHA-bound Stage 13 Development metrics; a real Docker mT5 structural probe with matching dependency snapshot and measured cgroup memory; and human-reviewed representative real document, fixed Stage 10 semantic gates and security evidence.

The release screen **never** returns Production GO. With missing/invalid evidence it reports `NO_GO` (exit 2). With all evidence checks green, it returns only `MANUAL_SIGNOFF_REQUIRED` (exit 3). These intentionally nonzero codes must not be treated as an automatic deploy success. The public visibility option remains blocked because this project does not implement built-in auth/rate limiting. Reports are newly created, **never overwritten**, and contain no private raw evidence.

Run with your previously generated Stage 13 Development JSON:

```powershell
.\.venv\Scripts\python.exe -m benchmarks.production_release_gate --development-report ".\local_stage13_query_dev_metrics_v1.json" --output ".\local_production_gate_initial_v1.json"
Get-Content -LiteralPath ".\local_production_gate_initial_v1.json" -Raw
```

**Expected now: `NO_GO`**, since real-model probe and independent human review evidence are absent. After the model probe, re-run with a **different output filename** and `--model-report ".\local_production_model_probe_v1.json"`; the human gate will still block release.

### Genuine independent human assessment

`docs/PRODUCTION_REVIEW_TEMPLATE.json` contains **unfilled/null** values. It is neither an approval nor fabricated sample measurements. Copy it to an ignored local file:

```powershell
Copy-Item -LiteralPath ".\docs\PRODUCTION_REVIEW_TEMPLATE.json" -Destination ".\local_production_human_review_v1.json"
# After authorized independent annotation:
# (Get-FileHash -Algorithm SHA256 -LiteralPath "PATH_TO_PRIVATE_REVIEW_EVIDENCE").Hash.ToLowerInvariant()
```

Reviewers must inspect genuine authorized Persian documents and exact source anchors, validate labeled answerable/no-answer/contradictory queries, and independently score mT5 generated atomic claims on the **frozen** Stage 9/10 protocol. The human-review manifest binds its private evidence by SHA-256; actual source and reviewer identities should remain local and never be committed.

The frozen Stage 10 Development gates remain: synthetic medium **≥8/19** facts, zero critical direction inversions and distorted facts, unsupported claims **≤12.5%** with reviewer-approved atomic segmentation, **≥3/5** distinct short/long cases; real-project medium **≥3/6** facts with zero critical fabrications; **0** duplicate four-grams for the specified architecture case. Latest measured real-project medium **2/6** is still below threshold. Do not invent new scores, change reference cases or use sealed Holdout for tuning.

When *real* independent review exists, the gate can read it using the optional arguments `--human-review local_production_human_review_v1.json` and `--review-evidence PATH_TO_PRIVATE_REVIEW_EVIDENCE`. User-reported reviewer metadata and hashes are attestations, **not cryptographic proof of independence**. A separately accountable release authority must still make a manual decision. Stage 9's proposed 30–50 documents, ≥100 queries and Recall@3 ≥0.90 are conservative sample/quality screens, **not previously validated production performance guarantees**.

## D. Remaining blockers and safety boundary

- Independently reviewed mT5 factual quality, explicit Stage 10 frozen-gate pass and representative real-Persian source semantics.
- Actual new constrained Docker build, generative cold/warm mT5 execution, measured process/cgroup peak and realistic load/timeout behavior.
- Signed dependency/image SBOM, CVE/license/advisory review, immutable base and wheel-hash/integrity verification.
- Security/authentication/gateway and a fresh threat model before **any publicly exposed deployment**.

**No new Docker image was built, model weights downloaded, GHCR image published, production service deployed, or real private document processed in this chat. Production status: NO-GO.**

## E. Verified Windows + pinned Docker real-model probe (2026-11-03)

**Updated verification:** The previously documented "NOT RUN" steps above were **run on the user's Windows + Docker Desktop system** after pulling `main` at `7e4a32d5ab3bf9961d420ffbe1cb40d76e389f63`. They are preserved as historical pre-run instructions, while this section reflects verified current evidence. **Overall Production remains NO-GO**.

### Engineering and constrained Docker

- Targeted release/Stage13/Stage8 regression: **48 passed, 0 failed, 1 third-party warning in 5.20s**. Full regression: **502 passed, 0 failed, 2 third-party warnings in 14.07s**. `pip check` succeeded; `compileall` reported no errors.
- Constrained `docker build --progress=plain -t mt5-persian-summary:prod-candidate .` **succeeded**; installed packages matched prior locked version snapshot, with `torch 2.15.0+cpu`, `pypdf 6.21.4`, `transformers 4.57.6`. New image manifest-list digest: `sha256:990804bc1769f2cca4e50839e5832190908f24478e8c562b766a2a8cfab973db`.
- The new candidate `mt5-prod-candidate` (ID prefix `2425662fe784`) started with 8 GiB memory, 2 CPUs, 256 PIDs, no-new-privileges and **loopback-only** `127.0.0.1:8004`. Health endpoint replied HTTP 200 `{"status":"ok"}`. Initial Docker health was `starting` seconds after creation, not a failed health result.

### Real mT5 inference and resource results

The opt-in `tests/production_model_probe.py` returned `status=STRUCTURAL_PASS`, `model_inference_exercised=true`, and **four actual text-summarization HTTP 200 responses** on one synthetic Persian sample.

| Phase | Elapsed (milliseconds) | Output characters |
| --- | ---: | ---: |
| First observed | **39,631.82** | 68 |
| Warm repeat | **5,790.75** | 68 |
| Concurrent request 1 | **6,378.61** | 68 |
| Concurrent request 2 | **10,681.34** | 68 |

All four output SHA-256s were identical: `c9c9e0ddb6c8f99e752ce1efc2d563a6d238fd9669f90948974d6e191d111995`. This confirms **output consistency only for this identical synthetic input**, not semantic correctness. "First observed" is **not guaranteed cold start**. Parallel admission showed two successful callers, not proof of a traffic/SLA limit or wide concurrency capacity.

The Linux container cgroup before inference: `current_bytes=60,055,552`, `peak_bytes=65,036,288`. After inference: `current_bytes=1,163,972,608`, **lifetime `peak_bytes=1,168,732,160`** (~1.09 GiB) against `limit_bytes=8,589,934,592` (8 GiB). This is a cgroup lifetime high-water mark on a small synthetic workload, **not a standalone peak host RSS or worst-case memory footprint**.

Runtime `dependency_snapshot.status=MATCH`, `pin_count=48`, `mismatch_names=[]`, and constraints SHA-256 `479795f6103a79cdaf9403cac4c0b13a7a867ea7fca5a16fabf6f1bca8178a06`. This confirms runtime version parity; it does **not** replace wheel-hash, CVE or license assurance.

### Automated release decision

With `local_stage13_query_dev_metrics_v1.json` and `local_production_model_probe_v2.json`, the user ran the release gate and obtained:

```json
{
  "decision": "NO_GO",
  "production_go": false,
  "checks": {
    "frozen_development_metrics": true,
    "real_model_http_and_cgroup_memory": true,
    "private_only_deployment": true,
    "independent_real_document_review": false
  },
  "blocked_checks": ["independent_real_document_review"]
}
```

This is the **expected and correct fail-closed result**. The model/memory packaging check now passes; an independently verified, representative Persian factual and evidence review is still **NOT RUN**. The last frozen Stage 10 real-project medium fact coverage remained **2/6 vs required ≥3/6** with no new adjudication, so no assertion of model factual quality has been earned. Even a future all-true machine screen returns `MANUAL_SIGNOFF_REQUIRED` with `production_go=false`, never an automatic deploy authorization.

### Next verification and non-waivable blockers

1. Collect **authorized** representative Persian TXT, selectable-PDF and DOCX documents (~30–50) and **≥100** labeled questions covering positive, missing, conflicts, dates, people and amounts; independently judge supporting quotes and the model's atomic factual claims. Keep originals/reviewer identities local, hash the private review evidence, fill `docs/PRODUCTION_REVIEW_TEMPLATE.json` only with actual results.
2. Reassess the frozen Stage 10 summarization quality gates without changing thresholds, Development labels or opening sealed Holdout to tune. The latest measured medium real-project score **2/6** has not met **≥3/6**.
3. Perform separately scoped authenticated gateway/rate-limiting, load/long-document resource characterization and software supply-chain security review before any public endpoint or production release.

**New work in this update is documentation-only.** No further Docker build, model call, benchmark, human approval, GHCR publication or deployment was performed by the assistant; the user supplied the test and probe evidence. Current status: **Production Readiness In Progress / NO-GO**, Stage 13 Development **Completed**.

## F. Exploratory real-format Document Query quality regression and follow-up (2026-11-04)

A user executed a blind, local **five-document / 25-question** evaluation against the previously verified `mt5-prod-candidate` image. The baseline `local_production_qa25/responses_v1.json` recorded **25/25 HTTP 200**, **4 `found` / 21 `not_found`**. Qualitative source checking indicated Q12 fully correct, Q03 incomplete, Q08 and Q09 selecting incorrect adjacent numerical snippets; HTTP integrity is not answer correctness. The user-authored documents are legal/public-source *rewrites* and the 25 cases do not establish independent representative Production quality. The private ZIP, answer key and raw review CSV **must remain outside Git**.

**Remediation:** An isolated post-Stage-13 Search fix in `DocumentRetrievalService` and `DocumentQueryService` adds more flexible Persian lexical normalization, corpus-local rare-term scoring, bounded same-paragraph DOCX topic context, amount-versus-percentage relevance and multi-part original-source excerpt selection. No external model/vector index, generative answers, upload validation bypass or API format change. Existing conservative `not_found`/`ambiguous` semantics and original-evidence contracts are retained; correctness on unseen data and realistic PDF RTL extraction still require testing.

**Test claims boundary:** The assistant verified 8 new tests against an isolated local source-class harness and 15/15 frozen Stage 11 Development query matches using a stand-in extractor. Neither is a complete GitHub CI run. The new code has **not** yet been exercised in Docker by the user, nor has `responses_v2.json` been generated. A higher `found` rate is **not** a factual correctness score. The frozen Stage 10 minimum real-project medium coverage **3/6** versus prior **2/6**, independent human review, and public exposure/security release criteria are unchanged. **Production remains NO-GO**.

Use the latest `main` and the already provided `local_production_qa25/run_persian_qa25.py` and input files. Keep the old production candidate container intact. From the repository root in Windows PowerShell:

```powershell
git pull --ff-only origin main
.\.venv\Scripts\python.exe -m compileall -q src benchmarks tests
.\.venv\Scripts\python.exe -m pytest -q tests/test_stage11_retrieval.py tests/test_stage12_document_query.py tests/test_stage13_quality.py
.\.venv\Scripts\python.exe -m pytest -q
docker build --progress=plain -t mt5-persian-summary:search-fix .
# Use a new container name/port; do not remove, rename or overwrite the previous prod candidate:
docker run -d --name mt5-search-fix --init --memory 8g --cpus 2 --pids-limit 256 --security-opt no-new-privileges -p 127.0.0.1:8005:8000 -v mt5_hf_cache:/home/app/.cache/huggingface -e env_type=production mt5-persian-summary:search-fix
curl.exe -sS http://127.0.0.1:8005/api/v1/health
.\.venv\Scripts\python.exe .\local_production_qa25\run_persian_qa25.py qa --archive .\local_production_qa25\persian_5_documents_25_qa.zip --questions .\local_production_qa25\questions_only.txt --base-url http://127.0.0.1:8005 --output .\local_production_qa25\responses_v2.json
.\.venv\Scripts\python.exe .\local_production_qa25\run_persian_qa25.py review --results .\local_production_qa25\responses_v2.json --answer-key .\local_production_qa25\answer_key_25_questions.json --output .\local_production_qa25\review_v2.csv
```

If a name/port is already in use, **inspect first** rather than replacing a running container. Review `review_v2.csv` question by question, including no-answer/ambiguous cases, exact source positions, multi-fact coverage and dates/amounts. **Do not** write semantic labels until independently checked; do not alter frozen signoff thresholds or tune on sealed Holdout. Future production consideration requires a genuinely independent dataset and original Stage 10 pass.

## G. Round-3 source-grounded multi-fact query repair (2026-11-04)

The previously deployed Docker `search-fix` passed 510 Windows tests and real 25/25 source HTTP responses; independent semantic pass is **not established**. Assistant review of `responses_v2.json` marked 16 fully supported and complete, seven incomplete, one topical nonanswer and one false `ambiguous` Q17. This is an exploratory, user-provided, non-independent dataset; never insert reference answers into the service.

The minimal round-3 patch extends answer mode across adjacent *verbatim extracted* sentences of a single TXT/DOCX paragraph or a short PDF page-local section without crossing a recognized heading. It preserves source location, ordering, word-for-word excerpts, existing evidence/API DTOs, source quote validation and a total 1,200-character answer budget. Section heading terms can help rank and admit otherwise incomplete lexically matched passages, but headings are not used as invented answer text. Numerical/person conflicts now require a near-identical claimed subject; unrelated fiscal metrics (revenue versus operating profit) are not logically conflicting. True contradictory budget/date/person claims remain abstentions. PDF repair is restricted to obviously impossible reversed four-digit years after Persian month names; extraction may still vary by PDF generator and PyPDF version. No OCR or model change.

**Verification boundary:** 8/8 new local isolated source-class tests passed; a representative-extraction trial over the supplied five documents/25 questions found promising excerpt coverage; an approximate frozen Development Stage 11 check retained 15/15 source quote matches. These are **not** current-source Windows suite, CI, a re-built Docker regression, human quality score, or a Production GO. Eleven synthetic regression tests were added to Stage 11/12 test modules; the actual GitHub test suite must be run on user Windows before quality claims.

### Local Windows PowerShell verification, from repository root

```powershell
git pull --ff-only origin main
$env:env_type = "development"
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m compileall -q src benchmarks tests
.\.venv\Scripts\python.exe -m pytest -q tests/test_stage11_retrieval.py tests/test_stage12_document_query.py tests/test_stage13_quality.py
.\.venv\Scripts\python.exe -m pytest -q
docker build --progress=plain -t mt5-persian-summary:query-context-v3 .
docker ps -a --filter "name=mt5-query-context-v3"
Get-NetTCPConnection -State Listen -LocalPort 8006 -ErrorAction SilentlyContinue
# Only when the container name and port are unused:
docker run -d --name mt5-query-context-v3 --init --memory 8g --cpus 2 --pids-limit 256 --security-opt no-new-privileges -p 127.0.0.1:8006:8000 -v mt5_hf_cache:/home/app/.cache/huggingface -e env_type=production mt5-persian-summary:query-context-v3
curl.exe -sS http://127.0.0.1:8006/api/v1/health
.\.venv\Scripts\python.exe .\local_production_qa25\run_persian_qa25.py qa --archive .\local_production_qa25\persian_5_documents_25_qa.zip --questions .\local_production_qa25\questions_only.txt --base-url http://127.0.0.1:8006 --output .\local_production_qa25\responses_v3.json
.\.venv\Scripts\python.exe .\local_production_qa25\run_persian_qa25.py review --results .\local_production_qa25\responses_v3.json --answer-key .\local_production_qa25\answer_key_25_questions.json --output .\local_production_qa25\review_v3.csv
```

Examine Q01/Q03/Q04/Q11/Q15/Q16/Q17/Q18/Q21 first, then audit all questions (including any newly found false positives, unsupported answers, source location and date/order fidelity). Do not overwrite `responses_v1.json` or `responses_v2.json`. Do not stop/remove the previously verified containers by default. Production remains **NO_GO** due to original Stage 10 factual quality gate, independent review and deployment/security prerequisites.

## H. Answer validation and abstention hardening (2026-11-04)

**Status:** Development patch only — **PRODUCTION NO-GO**. User-local round-3 engineering tests passed 521/521, but a newly written synthetic five-document/25-question challenge showed repeated *unsupported* "found" and missed multi-paragraph facts. The new synthetic set was consulted while diagnosing this round, so its future results count as **regression**, not independent blind validation.

The patch introduces a small, model-free `DocumentAnswerValidator` that distinguishes mere topical overlap from evidence of the requested answer type. Unsupported contract identifiers, equipment models, supplier names, and IP addresses are rejected even if nearby amounts or dates exist. Conditional-time queries may be supported by an explicit "only after / subject to" condition rather than a calendar date. If a question requests an enumerated answer, an introduction alone is not enough evidence. Ambiguous competing rates of the *same* metric within one period are reported with the two source quotations. Different metrics and periods are not assumed contradictory. Context gathering for multipart DOCX questions is bounded within the same styled section, with unchanged 1200-character answer limit. No user answer keys or expected values enter source code, and the REST DTO is unchanged.

**Assistant isolated pre-commit evidence:** 21/21 synthetic regression assertions passed; stand-in extractor replay of the newly authored five documents matched 20/4/1 expected statuses, and the prior 25-question set returned all 25 `found`. The semantic score on unreviewed future documents is **unknown**; no guarantee of complete semantic answer validation. No official full checkout tests, new Docker E2E, Stage10 quality signoff, CI or independent human scoring have yet been performed.

### Required Windows PowerShell validation

```powershell
git pull --ff-only origin main
git rev-parse HEAD
$env:env_type = "development"
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m compileall -q src benchmarks tests
.\.venv\Scripts\python.exe -m pytest -q tests/test_answer_validation.py tests/test_stage11_retrieval.py tests/test_stage12_document_query.py tests/test_stage13_quality.py
.\.venv\Scripts\python.exe -m pytest -q
docker build --progress=plain -t mt5-persian-summary:answer-validation-v4 .
docker ps -a --filter "name=mt5-answer-validation-v4"
Get-NetTCPConnection -State Listen -LocalPort 8008 -ErrorAction SilentlyContinue
# Only with unused port and name:
docker run -d --name mt5-answer-validation-v4 --init --memory 8g --cpus 2 --pids-limit 256 --security-opt no-new-privileges -p 127.0.0.1:8008:8000 -v mt5_hf_cache:/home/app/.cache/huggingface -e env_type=production mt5-persian-summary:answer-validation-v4
curl.exe -sS http://127.0.0.1:8008/api/v1/health
.\.venv\Scripts\python.exe .\local_production_qa25\run_persian_qa25.py qa --archive .\local_production_qa25\final_blind_persian_5docs_25q.zip --questions .\local_production_qa25\questions_final_only.txt --base-url http://127.0.0.1:8008 --output .\local_production_qa25\responses_final_v4.json
.\.venv\Scripts\python.exe .\local_production_qa25\run_persian_qa25.py review --results .\local_production_qa25\responses_final_v4.json --answer-key .\local_production_qa25\answer_key_final_25.json --output .\local_production_qa25\review_final_v4.csv
```

The old containers and responses must remain intact for comparison. Human review must check *both* statuses and all requested atomic facts, not just number of `found`. Hold the original Production gate until model-specific factual quality, truly independent evaluation, and security/operational release criteria pass.
