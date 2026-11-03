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
