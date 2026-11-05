# mT5 Persian Summarization Service

**A FastAPI REST API for Persian text summarization and source-grounded document questions.**

Summarize Persian text, process TXT/PDF/DOCX documents, or ask questions about a document with source citations. Run locally with Docker Compose or Python and explore the API through Swagger.

> [!IMPORTANT]
> **Development software — not approved for production.** mT5 summaries may omit important decisions, dates, amounts, or names and may be unexpectedly short. Always review generated summaries against original documents. The service has no built-in authentication for public access.

## Features

| Feature | Behavior |
| --- | --- |
| Text summarization | JSON text to a generated mT5 summary |
| File summarization | One UTF-8 `.txt`, text-based `.pdf`, or `.docx` |
| Multi-file summarization | 1–32 files; each file gets a separate result |
| Summary lengths | `short`, `medium`, `long` (output ceilings, **not** guaranteed lengths) |
| Document questions | Extract original evidence, or return `not_found` or `ambiguous` |
| Focused summaries | Topic-relevant **source excerpts**, not mT5-generated text |
| Long documents | Token-aware chunking and bounded hierarchical summarization |
| API documentation | Swagger `/docs` and OpenAPI `/openapi.json` |

**Unsupported:** OCR/scanned-image PDFs, legacy Word `.doc`, image uploads, authentication, a browser UI, permanent document storage, background jobs, and fine-tuning. Document Query is conservative lexical retrieval, not general conversational AI.

## Quick start: Docker Compose (recommended)

Install [Git](https://git-scm.com/) and [Docker Desktop](https://www.docker.com/products/docker-desktop/) or Docker Engine with Compose.

~~~bash
git clone https://github.com/Amirmahdimtz/mT5-Persian-Summary.git
cd mT5-Persian-Summary
docker compose up --build -d
docker compose ps
~~~

Then open **http://127.0.0.1:8000/docs** in a browser. Check the service:

~~~bash
curl http://127.0.0.1:8000/api/v1/health
docker compose logs --tail 100 summarizer
~~~

Expected response: `{"status":"ok"}`. This tests HTTP/process **liveness only**, not mT5 readiness.

The current `compose.yaml` builds your **current checkout**, binds port **8000** to localhost, persists model downloads in the `hf_cache` Docker volume, and sets an 8 GiB container memory **limit** by default (not a measured minimum). The image does **not** include model weights. The first mT5 summarization request needs Hugging Face access unless weights are cached; document questions do not invoke mT5.

~~~bash
# Stop the service when finished:
docker compose down
~~~

> The published `ghcr.io/amirmahdimtz/mt5-persian-summary:stage8` image is **legacy** and must not be assumed to contain Document Query. Build from this repository for all current features.

## Run from source (Python)

Python **3.12** is used in the Dockerfile and recent user-verified Windows tests. The commands below run Uvicorn on port **8001**; Docker Compose uses **8000**.

### Windows PowerShell

~~~powershell
git clone https://github.com/Amirmahdimtz/mT5-Persian-Summary.git
cd mT5-Persian-Summary
py -3.12 -m venv .venv

# Run the venv executable directly; activation is optional.
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install 'torch>=2.6,<3.0' --index-url https://download.pytorch.org/whl/cpu
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip check

$env:env_type = "development"
.\.venv\Scripts\python.exe -m uvicorn src.host.app:app --host 127.0.0.1 --port 8001 --workers 1
~~~

Open **http://127.0.0.1:8001/docs**. Leave the server terminal open; press **Ctrl+C** to stop it. If you already cloned the repository, work in that checkout rather than cloning again.

**After `git pull --ff-only origin main`, restart Uvicorn.** Without `--reload`, an already running process uses its previously loaded code.

### Linux / macOS

~~~bash
git clone https://github.com/Amirmahdimtz/mT5-Persian-Summary.git
cd mT5-Persian-Summary
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip check

export env_type=development
python -m uvicorn src.host.app:app --host 127.0.0.1 --port 8001 --workers 1
~~~

For CPU-only Linux hosts, consider installing PyTorch from the [official CPU wheel index](https://download.pytorch.org/whl/cpu) before the requirements, as the Dockerfile does. On macOS, use a compatible PyTorch distribution. Native Linux/macOS runs are less extensively verified than the Docker and Windows workflows.

## API reference

All endpoints are prefixed with `/api/v1`:

| Endpoint | Request | Purpose |
| --- | --- | --- |
| `GET /health` | None | Process liveness |
| `POST /summarization/text` | JSON | Generative mT5 summary of pasted text |
| `POST /summarization/file` | Multipart `file`, optional `summary_length` | Generative summary of one file |
| `POST /summarization/files` | Repeated multipart `files`, optional `summary_length` | Independent summaries for multiple files |
| `POST /document_query/file` | Multipart `file`, `query`, `mode`, optionally `summary_length` | Extractive answer or focused source summary |

**Swagger:** open `/docs`, expand the endpoint, click **Try it out**, supply request fields, click **Execute**, and inspect the HTTP status and JSON response. Examples below assume a **Python server on port 8001**. If using Docker Compose, replace `8001` with `8000`.

### 1. Summarize Persian text

Use `POST /api/v1/summarization/text` with:

~~~json
{
  "text": "جلسه هماهنگی برگزار شد و اعضا مقرر کردند گزارش نهایی تا پایان هفته تهیه شود.",
  "summary_length": "medium"
}
~~~

PowerShell:

~~~powershell
$body = @{ text = "جلسه برگزار شد و اعضا تهیه گزارش نهایی تا پایان هفته را تصویب کردند."; summary_length = "medium" } | ConvertTo-Json -Compress
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8001/api/v1/summarization/text" -ContentType "application/json; charset=utf-8" -Body ([System.Text.Encoding]::UTF8.GetBytes($body))
~~~

The response includes `summary`, `summary_length` and character counts. There is no predetermined output; this is generated text.

### 2. Summarize one document

In Swagger choose `POST /api/v1/summarization/file`, upload a TXT, searchable PDF or DOCX file and select `summary_length`.

PowerShell (replace `minutes.docx` with an existing local file):

~~~powershell
curl.exe --fail-with-body -F "file=@minutes.docx;type=application/vnd.openxmlformats-officedocument.wordprocessingml.document" -F "summary_length=medium" "http://127.0.0.1:8001/api/v1/summarization/file"
~~~

On success, inspect `success: true`, `summary` and `input_characters` / `output_characters`. A successful request does not guarantee an accurate summary.

### 3. Summarize multiple files

~~~powershell
curl.exe --fail-with-body -F "files=@minutes.docx;type=application/vnd.openxmlformats-officedocument.wordprocessingml.document" -F "files=@notes.txt;type=text/plain" -F "summary_length=long" "http://127.0.0.1:8001/api/v1/summarization/files"
~~~

Both local files must exist. The result contains `results`, `succeeded` and `failed`. Inspect the per-file `success` and `error_code`, **even if HTTP returns 200**. The files are **not** merged into a single summary.

### 4. Ask a question about a document

In Swagger, select `POST /api/v1/document_query/file`, then:

| Field | For source-grounded Q&A |
| --- | --- |
| `file` | A real TXT/PDF/DOCX document |
| `query` | e.g. `تاریخ جلسه چه بود؟` |
| `mode` | `answer` |
| `summary_length` | **Leave blank** / **Send empty value** |

PowerShell:

~~~powershell
curl.exe --fail-with-body -F "file=@minutes.docx;type=application/vnd.openxmlformats-officedocument.wordprocessingml.document" -F "query=تاریخ جلسه چه بود؟" -F "mode=answer" "http://127.0.0.1:8001/api/v1/document_query/file"
~~~

**Do not send `summary_length=short` (or any nonempty length) with `mode=answer`:** the API intentionally returns **HTTP 422 / InvalidSummaryLength**.

Document Query uses exact source excerpts, **not mT5 generation**. Its HTTP response can be `200` in all three cases:

| `status` | Meaning |
| --- | --- |
| `found` | `answer` contains quoted source text, and `evidence` identifies page/paragraph/table location |
| `not_found` | `answer=null`, `evidence=[]`; no sufficiently supported answer |
| `ambiguous` | `answer=null` with competing source excerpts in `evidence` |

This retriever is conservative: questions worded very differently from the document, ambiguous terms, or awkward PDF/table extraction can yield `not_found` even if a human can locate the fact. Prefer concise, source-aligned questions.

### 5. Focused summary from original document excerpts

On the **same** endpoint, use `mode=focused_summary` and a length:

~~~powershell
curl.exe --fail-with-body -F "file=@minutes.docx;type=application/vnd.openxmlformats-officedocument.wordprocessingml.document" -F "query=مصوبات و اقدامات پیگیری جلسه" -F "mode=focused_summary" -F "summary_length=long" "http://127.0.0.1:8001/api/v1/document_query/file"
~~~

This is **extractive** source selection, not an mT5 summary. For a generated summary use `/summarization/file`.

### Linux/macOS curl equivalents

~~~bash
curl --fail-with-body -H 'Content-Type: application/json; charset=utf-8' --data '{"text":"جلسه برگزار شد و مهلت تهیه گزارش مشخص شد.","summary_length":"medium"}' http://127.0.0.1:8001/api/v1/summarization/text
curl --fail-with-body -F 'file=@minutes.docx;type=application/vnd.openxmlformats-officedocument.wordprocessingml.document' -F 'query=تاریخ جلسه چه بود؟' -F 'mode=answer' http://127.0.0.1:8001/api/v1/document_query/file
~~~

For multipart requests, let curl generate the `Content-Type` boundary instead of setting the header manually.

## Limits and response semantics

**Summary length controls the maximum output budget, not the minimum.** The model may stop early and return identical results for `medium` and `long`.

| `summary_length` | Maximum final mT5 tokens | Max. focused source summary characters |
| --- | ---: | ---: |
| `short` | 40 | 320 |
| `medium` (default) | 80 | 680 |
| `long` | 120 | 1,200 |

| Input or resource | Limit |
| --- | --- |
| Direct JSON text | Nonblank, 1–200,000 characters |
| File formats | UTF-8 TXT, searchable PDF, DOCX; no OCR |
| Individual file | 20 MiB |
| Batch size | 1–32 files |
| Total uploaded file bytes | Default 32 MiB per request |
| `query` | 1–512 characters |
| Model input per inference | Up to 1,000 tokens; chunking handles longer documents |
| Default inference concurrency | One at a time, per process |
| Default model queue admission | 30 seconds (not a generation timeout) |

| HTTP code | Typical cause |
| --- | --- |
| `200` | Processed; inspect `status` or per-file `success` |
| `400` | Invalid filename or empty upload |
| `408` | Stalled multipart upload |
| `413` | File, body, aggregate or work budget exceeded |
| `415` | Unsupported extension/MIME type |
| `422` | Invalid query, fields, or mode/length combination |
| `500` | Unexpected parsing or inference failure |
| `503` | Model unavailable or admission capacity exhausted |

Errors generally use a JSON `detail` with `code` and `message`. HTTP 200 does **not** imply semantic correctness.

## Configuration and model

Configuration files:

- [`src/host/res/appsettings.yaml`](src/host/res/appsettings.yaml): non-development / Docker settings.
- [`src/host/res/appsettings.development.yaml`](src/host/res/appsettings.development.yaml): development settings.

Set `env_type=development` (or `ENV_TYPE=development`) for development mode. `production` uses the base YAML. Do not assume undocumented environment overrides such as `MODEL_ID` exist.

| Configuration | Checked-in value |
| --- | --- |
| Checkpoint | [`nafisehNik/mt5-persian-summary`](https://huggingface.co/nafisehNik/mt5-persian-summary) |
| Model revision | `b575560ad967050e77a40f907abb1ebbeefb9a15` |
| Device | CPU |
| Max. input / output tokens | 1,000 / 120 |
| Generation | `num_beams=2`, `do_sample=False`, `early_stopping=True` |
| Length penalty | `2.0` |
| Development repeat guard | `no_repeat_ngram_size=3` (base config: `0`) |

This repository integrates a pinned, previously trained mT5 encoder-decoder model; it does **not** fine-tune it. The weights are loaded lazily. The provided Dockerfile uses one worker to limit duplicate model memory.

## Troubleshooting

| Symptom | Recommended check |
| --- | --- |
| Swagger unavailable | Check Uvicorn/Docker logs and port: `8000` with Compose, `8001` with Python examples. |
| `422 InvalidSummaryLength` | Leave `summary_length` empty with Document Query `mode=answer`; use it only in `focused_summary`. |
| `not_found` for a fact in the document | Confirm extractable text and ask a more precise question using source terminology. |
| Identical `medium` and `long` | Output length is a ceiling; short output is a known model-quality limitation. |
| Scanned PDF has no useful result | OCR is not supported; supply a text-searchable PDF or DOCX. |
| First summary slow / `503` | Check Hugging Face access, model cache, free disk, RAM and logs. Health is not model readiness. |
| Changes after pull not visible | Restart Uvicorn or rebuild/restart the Docker service. |
| `413` | Reduce document/file size or adjust reviewed upload budgets. |
| Another device cannot connect to localhost | The API is intentionally bound to `127.0.0.1`; do not expose it publicly without security controls. |

## Tests and quality status

Run from the repository root after installing dependencies:

~~~powershell
# Windows PowerShell
$env:env_type = "development"
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m compileall -q src tests benchmarks
.\.venv\Scripts\python.exe -m pytest -q
~~~

~~~bash
# Linux/macOS
export env_type=development
python -m pip check
python -m compileall -q src tests benchmarks
python -m pytest -q
~~~

Optional live Document Query smoke test against a running source server:

~~~powershell
.\.venv\Scripts\python.exe tests/e2e_document_query_smoke.py --base-url http://127.0.0.1:8001
~~~

**Latest user-verified Windows results (2026-11-05):** `pip check` and `compileall` passed, and **588 pytest tests passed** (two non-failing third-party deprecation warnings). A **synthetic, assistant-authored** 30-document/160-question TXT/PDF/DOCX Development regression set yielded 120/120 complete answerable cases, 0/40 false positives on abstention cases, and 39/40 on a strict abstention/evidence score. The strict remaining miss was a zero-width-non-joiner spelling difference (`باغ‌ها` vs `باغها`), even though the API returned `ambiguous` with both conflicting source excerpts.

**Scope of evidence:** These were exposed Development regression cases, **not** independent human-labelled real-world documents, and are **not a benchmark of mT5-generated summary fidelity**. The separate generative summarization factual-quality and operational/security production gates remain open. **Production NO-GO.**

Details: [Answer quality evaluation](docs/ANSWER_QUALITY_EVALUATION.md) and [Production readiness](docs/PRODUCTION_READINESS.md).

## Architecture and related documents

~~~text
src/
  host/                 FastAPI startup, YAML settings
  application/          Thin controllers, DTOs, HTTP validation
  core/services/        Extraction, retrieval, validation, chunking, orchestration
  infrastructure/       Dependency injection and mT5 provider
tests/                   Unit, integration and live HTTP smoke tests
benchmarks/              Development quality evaluation
docs/                    Progress and release documentation
Dockerfile               CPU Python 3.12 image
compose.yaml             Docker Compose configuration
requirements.txt         Python dependencies
~~~

The code follows feature-based controller discovery and constructor dependency injection.

- [Implementation progress](docs/IMPLEMENTATION_PROGRESS.md)
- [Architecture guide (Persian)](Service_Architecture_Guide_FA.md)
- [Implementation plan (Persian)](IMPLEMENTATION_PLAN.md)
- [Model verification](docs/STAGE2_MODEL_VERIFICATION.md)
- [Production readiness and release gates](docs/PRODUCTION_READINESS.md)

## Security and licensing

- **Run locally by default.** Authentication, multi-tenant isolation, and production-grade public access control are not provided. Do not expose the API to untrusted networks.
- Uploads may be buffered in memory or temporary bounded storage; the application does not intentionally store source documents permanently. Protect the host, cache, temporary files and logs.
- Use confidential company documents only with permission. Independently verify summaries before legal, medical, financial or other consequential use.
- Model rights and training-data rights are separate from application source rights. Review the [upstream model card](https://huggingface.co/nafisehNik/mt5-persian-summary). **This repository has no root `LICENSE` file in the checked revision; do not assume a permissive source redistribution license.**

---

[GitHub repository](https://github.com/Amirmahdimtz/mT5-Persian-Summary) · [Docker Swagger](http://127.0.0.1:8000/docs) · [Source Swagger](http://127.0.0.1:8001/docs)
