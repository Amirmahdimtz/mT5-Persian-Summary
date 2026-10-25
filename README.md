# mT5 Persian Summarization Service — MVP

FastAPI REST API for Persian text summarization using a pinned, lazily loaded mT5 checkpoint. Supports direct text, UTF-8 TXT, **text-layer** PDF, DOCX and per-file summaries for batches. Long inputs use tokenizer-aware chunking and bounded hierarchical summarization. Swagger is available at `/docs`. **No OCR, authentication, database, queue, UI or model fine-tuning** is included.

## Architecture and requirements

- `src/host/`: ASGI entry point and YAML configuration; `src/application/`: HTTP DTOs, controllers, upload admission and discovery.
- `src/core/services/summarization/`: extraction, chunking, hierarchy and orchestration; `src/infrastructure/`: constructor `@inject` discovery, configuration and process-scoped model provider.
- Python **3.11+** (`.python-version` declares 3.11; Windows acceptance used **3.12.10**). Docker uses **Python 3.12.10**, Debian Bookworm slim and CPU-only PyTorch.
- Major dependencies: FastAPI, Pydantic v2, Uvicorn, Transformers 4.x, PyTorch 2.x, SentencePiece, pypdf 6.x, python-docx 1.x, python-multipart, PyYAML, HTTPX and pytest. `requirements.txt` has version **ranges, not an immutable lockfile**; Docker rebuilds may resolve newer compatible wheels. The Docker CPU index is used for PyTorch to avoid CUDA-enabled wheel downloads.

## Local installation

Run all commands from the repository root. Model weights are **not** bundled with the source; the first valid inference needs Hugging Face access unless the exact revision is already cached.

### Windows PowerShell — Python 3.12

```powershell
git clone https://github.com/Amirmahdimtz/mT5-Persian-Summary.git
cd mT5-Persian-Summary
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install 'torch>=2.6,<3.0' --index-url https://download.pytorch.org/whl/cpu
python -m pip install -r requirements.txt
python -m pip check
$env:env_type = 'development'
python -m compileall -q src tests
python -m pytest -q
python -m uvicorn src.host.app:app --host 127.0.0.1 --port 8001 --workers 1
```

For an existing checkout use `git pull --ff-only origin main` instead of cloning. If PowerShell blocks activation, run `Set-ExecutionPolicy -Scope Process RemoteSigned` and activate again. Use a **second** PowerShell window for the HTTP checks; set `env_type` separately in each window if required. If port 8001 is in use, select another available port.

### Linux / macOS

```bash
git clone https://github.com/Amirmahdimtz/mT5-Persian-Summary.git
cd mT5-Persian-Summary
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
# Linux CPU-only: optionally install CPU PyTorch first as in the Dockerfile.
python -m pip install -r requirements.txt
python -m pip check
export env_type=development
python -m compileall -q src tests
python -m pytest -q
python -m uvicorn src.host.app:app --host 127.0.0.1 --port 8001 --workers 1
```

Linux CPU hosts may prefer `python -m pip install 'torch>=2.6,<3.0' --index-url https://download.pytorch.org/whl/cpu` **before** installing `requirements.txt`. macOS uses the supported PyTorch distribution for its platform; the Dockerfile targets Linux/CPU only. Python, wheel and system-library compatibility must be checked for the target platform.

## Docker (CPU, one worker)

Docker Engine / Docker Desktop with Compose v2 and sufficient disk/RAM is required. These commands are the Stage 8 **validation procedure**, not a claim that this repository's image has already been built on every platform. Docker Desktop must have enough memory assigned to run the configured container.

```powershell
docker build -t mt5-persian-summary:stage8 .
docker volume create mt5_hf_cache
docker run -d --name mt5-persian-summary --init --memory 8g --cpus 2 --pids-limit 256 --security-opt no-new-privileges -p 127.0.0.1:8000:8000 -v mt5_hf_cache:/home/app/.cache/huggingface -e env_type=production mt5-persian-summary:stage8
docker ps --filter name=mt5-persian-summary
docker inspect --format '{{json .State.Health}}' mt5-persian-summary
docker logs --tail 100 mt5-persian-summary
# Run the real HTTP smoke from the host virtual environment (see Testing).
docker stop mt5-persian-summary
docker rm mt5-persian-summary
```

Use these same `docker` commands in Bash on Linux/macOS. The image's `CMD` explicitly binds `0.0.0.0:8000` using **one Uvicorn worker**; the host publishes only `127.0.0.1:8000`, not a public interface. Port changes require changing the run/Compose host mapping, or the image command. The YAML `server.host` and `server.port` apply to `python -m src.host.app`, **not** the explicit Uvicorn Docker command. A published port is not an authentication boundary if an upstream proxy exposes the service.

For an equivalent single-service Compose deployment with a managed cache volume:

```powershell
docker compose up --build -d
docker compose ps
docker compose logs --tail 100 summarizer
docker compose down
```

`compose.yaml` defines exactly one service and one named volume. It defaults to an **8 GiB memory limit and 2 CPUs**; override planning limits using environment variables `MT5_MEMORY_LIMIT` and `MT5_CPUS` before `docker compose up`. These are preliminary resource allocations, **not measured model requirements or proof of safe peak usage**. `docker compose down` retains its named volume unless explicitly removed. The `docker run` volume `mt5_hf_cache` and the Compose project-scoped `hf_cache` volume are separate unless configured otherwise. Do **not** use `docker compose down -v` when cache preservation is desired.

Build copies `requirements.txt` before application code for dependency layer reuse, installs CPU-only PyTorch before other dependencies, excludes `.venv`, Git files, model files, local documents and tests from the build context, then executes under UID 10001 (`app`). Model artifacts are fetched **at inference time** into `HF_HOME=/home/app/.cache/huggingface` and kept on the writable named volume. A host bind-mounted cache must be writable by UID 10001; named volumes initialize from the prepared image directory. No Hugging Face token or secret is required for the public pinned checkpoint; never bake tokens, `.env` or credentials into an image. Use explicit `HF_HOME` volume persistence to avoid repeated downloads after container replacement.

**Four separate checks:** successful `docker build` means packaging succeeded; `docker ps` means the process/container started; Docker's healthcheck and `GET /api/v1/health` mean **HTTP liveness only**; only a successful `/summarization/text` or the opt-in real-model HTTP smoke verifies that the checkpoint was downloaded, loaded and could produce an inference. The first inference may take substantially longer because it downloads approximately 1.2 GB of weights and initializes the tokenizer/model. Startup and health do not preload weights. Failed model initialization is cached **within that process**; repair network/cache/permissions and restart the container to retry. With a complete verified cache, `HF_HUB_OFFLINE=1` can be set for offline inference; without the exact pinned files, offline first use returns HTTP 503.

A graceful Docker stop signals the PID 1 Uvicorn process (`--init` forwards signals), allowing normal ASGI graceful shutdown **subject to runtime grace periods and active work**. Python worker threads running `torch.generate` or document parsing cannot be forcibly stopped by coroutine cancellation, HTTP disconnect or SIGTERM. Do not assume that `docker stop` finishes long inference, or that an interrupted request instantly releases GPU/CPU/RAM resources. Keep one worker: each additional worker independently holds model weights and admission limits. `--memory` bounds container memory but can cause an OOM kill; it does **not** prove readiness.

## Configuration and resource policy

`env_type=development` selects `src/host/res/appsettings.development.yaml`. Any other nonempty `env_type` (including Docker's `production`) selects `appsettings.yaml`; uppercase `ENV_TYPE` is accepted if `env_type` is unset. Settings are **YAML-backed**, not arbitrary environment overrides: model ID, device, port and guards should be edited in the applicable file, not by inventing `MODEL_ID` or other unsupported environment keys. `HF_HOME` is consumed by Hugging Face libraries; Docker uses it for a writable persistent cache. Local default cache is typically `~/.cache/huggingface` (Windows: `%USERPROFILE%\.cache\huggingface`) unless overridden. `model.device` is `cpu` in both supplied profiles; `cuda` and `auto` exist in the provider but the supplied Docker image is CPU-only.

| Guard | Current value / behavior |
|---|---|
| Text request | Nonblank, at most **200,000 Unicode characters** (`422` if invalid); normalization can change whitespace |
| Per file | **20 MiB** source bytes; TXT UTF-8/BOM; text PDF and DOCX |
| Multi-file | **1–32** files, independent ordered results; batches processed sequentially |
| Aggregate files | **32 MiB** across files by default (`api.upload.max_total_bytes`, configurable 20–64 MiB), plus **1 MiB** multipart framing allowance at raw-body boundary |
| Upload buffering | Read in at most **64 KiB** chunks; request pre-spooled with 1 MiB RAM threshold and temporary disk; no application-level permanent file storage |
| Active multipart requests | **2** per process (`api.upload.max_active_requests`, allowed 1–16); busy admission may return `503` |
| Idle multipart stream | **30 seconds** between request-body chunks (`api.upload.idle_timeout_seconds`, allowed 1–300); `408` on timeout |
| Model inference | **1** concurrent per process (`model.max_concurrent_inferences`, range 1–4); **30-second** admission wait (`model.queue_wait_seconds`, max 300), after which `503`; **not** an inference execution deadline |
| Model call | **1,000 input tokens** including specials and **20,000 characters** per chunk, max **120 decoder tokens** before summary-length mapping |
| Hierarchy | **64 chunks** per pass, **6 levels**, **128 model calls** per request; insufficient compression fails explicitly |
| Document extraction | **500 PDF pages**, **5,000,000 extracted characters**; DOCX **2,000 ZIP members**, **20 MiB per expanded member**, **80 MiB declared expanded total** |

Generation uses `num_beams=2`, `repetition_penalty=1.0`, `length_penalty=2.0`, `early_stopping=true`, `do_sample=false`; short/medium/long decoder-token ceilings are **40/80/120** respectively. These are upper limits, not target word counts. Inference may take a long time on CPU even after admission. There is no enforced overall inference wall-clock timeout or live throughput/peak-memory capacity benchmark. HTTP clients/proxies must use appropriate timeouts. The previous **1046.2 MiB** Windows process working-set observation was a single snapshot, **not** peak Docker RAM. Plan for ~8 GiB initially and measure on representative workloads; malicious PDF resource exhaustion is not fully ruled out by current guards.

Pinned Hugging Face checkpoint: `nafisehNik/mt5-persian-summary` revision `b575560ad967050e77a40f907abb1ebbeefb9a15`, model-card **MIT** license (training-data rights should be reviewed separately). Model is `MT5ForConditionalGeneration` via `AutoModelForSeq2SeqLM`, SentencePiece tokenizer, about 1.2 GB FP32 `pytorch_model.bin`, loaded once per process using `weights_only=True` and `trust_remote_code=False`. See `docs/STAGE2_MODEL_VERIFICATION.md` for provenance and pickle-weight supply-chain caveats.

## HTTP API and Swagger

After startup, `http://127.0.0.1:8001/docs` and `/openapi.json` show the three summarization endpoints (Docker host port: **8000**). `GET /api/v1/health` returns `200 {"status":"ok"}` independent of model state. There is **no model readiness endpoint**: the healthcheck cannot establish model availability or successful inference.

| Method | Path | Input | Result |
|---|---|---|---|
| `POST` | `/api/v1/summarization/text` | JSON `{ "text": "...", "summary_length": "medium" }` | `200` summary and character counts |
| `POST` | `/api/v1/summarization/file` | multipart field `file` and optional `summary_length` | `200` per-file result |
| `POST` | `/api/v1/summarization/files` | repeated multipart field `files`, optional `summary_length` | `200` ordered `results`, `succeeded`, `failed` |

`summary_length` is `short`, `medium` or `long` (default `medium`). Example response shapes below are illustrative **contract examples**, not reproducible model output:

```json
{"summary":"بارش باران در مناطق شمالی افزایش می‌یابد.","summary_length":"medium","input_characters":200,"output_characters":45}
```

```json
{"filename":"sample.txt","summary_length":"medium","success":true,"summary":"خلاصه فارسی","input_characters":200,"output_characters":11,"error_code":null,"error_message":null}
```

```json
{"results":[{"filename":"sample.txt","summary_length":"medium","success":true,"summary":"خلاصه فارسی","input_characters":200,"output_characters":11,"error_code":null,"error_message":null}],"succeeded":1,"failed":0}
```

HTTP `200` from `/files` does **not** imply all files succeeded: inspect each `success`, `error_code`, and the total counts. Missing or mismatched content type, bad filename, invalid or unreadable documents can fail before/after extraction. The following Bash `curl` examples require actual local input files:

```bash
curl --fail-with-body -H 'Content-Type: application/json; charset=utf-8' \
  -d '{"text":"سازمان هواشناسی از افزایش بارش باران در شمال کشور خبر داد.","summary_length":"short"}' \
  http://127.0.0.1:8001/api/v1/summarization/text
curl --fail-with-body -F 'file=@sample.txt;type=text/plain' -F 'summary_length=medium' \
  http://127.0.0.1:8001/api/v1/summarization/file
curl --fail-with-body -F 'files=@sample.txt;type=text/plain' -F 'files=@sample.pdf;type=application/pdf' \
  -F 'files=@sample.docx;type=application/vnd.openxmlformats-officedocument.wordprocessingml.document' \
  -F 'summary_length=long' http://127.0.0.1:8001/api/v1/summarization/files
```

Windows PowerShell UTF-8-safe request and native `curl.exe` examples:

```powershell
$json = @{ text = 'سازمان هواشناسی از افزایش بارش باران در شمال کشور خبر داد.'; summary_length = 'medium' } | ConvertTo-Json -Compress
Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8001/api/v1/summarization/text' -ContentType 'application/json; charset=utf-8' -Body ([System.Text.Encoding]::UTF8.GetBytes($json))
'این یک متن فارسی برای خلاصه‌سازی است.' | Set-Content -Encoding UTF8 sample.txt
curl.exe -F 'file=@sample.txt;type=text/plain' -F 'summary_length=short' http://127.0.0.1:8001/api/v1/summarization/file
# Requires real text-layer sample.pdf and real DOCX sample.docx in the working directory.
curl.exe -F 'files=@sample.txt;type=text/plain' -F 'files=@sample.pdf;type=application/pdf' -F 'files=@sample.docx;type=application/vnd.openxmlformats-officedocument.wordprocessingml.document' -F 'summary_length=medium' http://127.0.0.1:8001/api/v1/summarization/files
```

Expected status codes (error details use sanitized `{ "detail": { "code": "...", "message": "..." } }`):

- **400**: invalid/empty filename, empty uploaded file or malformed multipart framing.
- **408**: multipart body idle longer than configured timeout (not a summary-generation timeout).
- **413**: per-file/aggregate/body upload size, file count, chunk or other processing budget exceeded.
- **415**: unsupported extension or mismatched multipart MIME type (no `.doc`, scanned-image OCR, image or binary formats).
- **422**: missing/invalid JSON/form fields, invalid text length/summary tier, invalid UTF-8, corrupt/encrypted/unreadable PDF/DOCX, or other unprocessable input.
- **503**: unavailable model/tokenizer or saturated upload/inference admission. Model download/network/permission problems may need process restart.
- **500**: unexpected inference/parser error, returned as a generic message. Avoid putting document contents into application/proxy logs or issue reports.

## Testing and acceptance

Fast `pytest` tests include mocked provider/API unit cases and in-process integration/parser cases. The optional scripts perform **real inference** (may download weights) and **live HTTP E2E** (must have a running Uvicorn process or Docker container). These are **different evidence levels**.

```powershell
$env:env_type = 'development'
python -m pip check
python -m compileall -q src tests
python -m pytest -q
python -m pytest -q tests/test_stage8_delivery.py
python -m pytest -q -s tests/test_document_extraction_service.py -k smoke_
python -m src.infrastructure.ml.smoke_mt5_model
python -m src.infrastructure.ml.smoke_mt5_long_text
python -m src.infrastructure.ml.smoke_mt5_quality --sample all
# In another terminal, after starting Uvicorn at 8001:
python tests/e2e_http_smoke.py --base-url http://127.0.0.1:8001 --large-upload
# With Docker container (host-published port 8000):
python tests/e2e_http_smoke.py --base-url http://127.0.0.1:8000 --large-upload
```

`tests/e2e_http_smoke.py` synthesizes Persian TXT, text-layer PDF (test font/ToUnicode mapping) and DOCX in memory; it checks liveness/OpenAPI, all three summary lengths, all three file formats, batch results, sanitized malformed PDF, invalid filename, invalid tier and optionally HTTP 413. It **does not prove correctness on arbitrary third-party PDFs**, peak-RAM safety, 408 timeout behavior or 503 under real concurrent load. The model quality smoke uses heuristic checks for nonempty Persian outputs, not factual-grounding evaluation. The Stage 7 Windows baseline had **260 passed** in the full suite and successful real-model/HTTP samples; these historic results are **not Stage 8 or Docker results**. See `docs/IMPLEMENTATION_PROGRESS.md` for exact verification status.

## Limitations, troubleshooting and next-version backlog

- **First request hangs or 503:** check the pinned Hugging Face revision/network, offline flags, disk/cache mount permission and available RAM. Inspect `docker logs mt5-persian-summary` or `docker compose logs summarizer` (do not enable payload logging). HTTP health `200` is possible before model readiness. Fix the environment and **restart** to clear a cached model-load error. For offline use, prepopulate the exact revision in the persistent HF cache; do not expect offline first-run downloads.
- **Memory/CPU and latency:** CPU inference is expensive; the checkpoint is ~1.2 GB on disk, but peak memory can be higher. Start with a single worker and adequate RAM; Docker OOM kills require increasing available Docker Desktop/host memory or reducing load. Multiworker deployments duplicate the model. Live load/throughput and peak-memory profiling remain pending.
- **PDF/DOCX issues:** image-only/scanned PDF needs OCR (out of scope). PDF RTL recovery is heuristic; some glyph, spacing and font-map errors persist. Malicious PDFs can still consume excessive parser resources. DOCX headers/text boxes/tracked changes may be omitted. Only `.txt`, `.pdf`, `.docx` are accepted.
- **Summary fidelity:** a Stage 7 multitopic sample omitted healthcare/education and **incorrectly changed a reduction in air pollution to an increase**. A repeated long sample produced an extremely compressed summary. Nonempty-output tests do not establish factual faithfulness. Review important summaries against originals; no guarantee is made for medical, financial or legal uses.
- **Cancellation/shutdown:** async cancellation does not instantly abort `torch.generate` or a running parser thread. An incoming request may outlive HTTP disconnect; graceful shutdown is best effort. No end-to-end inference execution deadline or durable work queue is implemented.
- **Security:** no authentication or rate limiting; keep published ports on loopback or put behind an access-controlled gateway before exposing to untrusted users. Upload guards do not constitute a comprehensive malicious-PDF sandbox. No persistent document store, tokens or secrets are included. Hugging Face checkpoint uses a `.bin` weights artifact; `weights_only=True` reduces but does not eliminate supply-chain concerns.
- **Platform:** Docker ships Linux/CPU wheels; it does not enable CUDA. macOS and GPU support require a separate supported installation. `pip check` and `docker build` are useful compatibility gates; exact versions may evolve due to requirement ranges.

**Backlog (not in MVP):** evaluation of Persian factual consistency and real-world document fidelity, live concurrency/peak-memory benchmarking, stronger untrusted-file isolation, immutable dependency locking/SBOM, OCR, authentication/rate limiting, background queue, storage/database, metrics, optional GPU and model fine-tuning.