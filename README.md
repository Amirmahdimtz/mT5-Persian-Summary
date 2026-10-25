# Persian Text and Document Summarization with mT5

**Persian Document Summarization REST API · FastAPI · mT5 · Docker**

This project accepts Persian text or `TXT`, text-based `PDF`, and `DOCX` documents and returns a Persian summary using [`nafisehNik/mt5-persian-summary`](https://huggingface.co/nafisehNik/mt5-persian-summary). It also supports multiple documents in a single request, returning **a separate summary for each file**.

> **Status: completed and tested MVP.** A successful API response does **not** guarantee a faithful summary. The model can omit important details, misstate facts, or generate an excessively short summary for a long document. **Always compare the generated summary with the original source before business or organizational use.**

## Requirements at a glance

| Item | Details |
| --- | --- |
| Fastest setup | Docker Desktop or Docker Engine and the prebuilt image on GitHub Container Registry (GHCR) |
| Run from source | Python 3.12 and `requirements.txt` |
| Hardware | Inference currently runs on **CPU**; initially budget around **8 GiB of available memory** for Docker (engineering estimate, not measured peak usage) |
| Internet access | Required to pull the image and download the model weights from Hugging Face on first use, unless already cached |
| Interface | Interactive Swagger UI at `/docs`, or a regular HTTP REST API |
| Supported files | UTF-8 `.txt`, text-extractable `.pdf`, and `.docx`; scanned documents/OCR are not supported |

**Recommended:** If you just want to try the service, follow the Docker quick start. You do not need to clone the repository or install Python.

## 1. Quick start with Docker (recommended)

A prebuilt image is available through GHCR. Start Docker on the machine where you want to use the API, then run these commands in **Windows PowerShell**. The same `docker` commands work in a Linux/macOS shell.

```powershell
docker pull ghcr.io/amirmahdimtz/mt5-persian-summary:stage8

docker volume create mt5_hf_cache

docker run -d --name mt5-persian-summary --init --memory 8g --cpus 2 --pids-limit 256 --security-opt no-new-privileges -p 127.0.0.1:8002:8000 -v mt5_hf_cache:/home/app/.cache/huggingface -e env_type=production ghcr.io/amirmahdimtz/mt5-persian-summary:stage8
```

- `8002` is the **host port**, while `8000` is the **container port**. All Docker examples below use host port `8002`.
- Binding to `127.0.0.1` makes the API accessible **only from the host machine**, not directly from another laptop or phone.
- The `mt5_hf_cache` Docker volume retains downloaded model files across container restarts.
- **Model weights are not packaged into the Docker image.** The first real summarization request may take longer while downloading the approximately **1.2 GB checkpoint** and loading it into memory.
- If the container already exists but is stopped, use `docker start mt5-persian-summary` rather than running a second container with the same name. If it is running, you do not need to recreate it.

Check the container and HTTP health:

```powershell
docker ps --filter name=mt5-persian-summary
docker inspect --format '{{json .State.Health}}' mt5-persian-summary
curl.exe -i http://127.0.0.1:8002/api/v1/health
```

Once startup is complete, Docker should report `healthy` and the API should return HTTP `200` with:

```json
{"status":"ok"}
```

**Important:** `/api/v1/health` checks HTTP/process **liveness**, not model readiness. It does not confirm that the model has downloaded or can generate a summary.

Open the Swagger UI in your Windows browser:

```powershell
Start-Process "http://127.0.0.1:8002/docs"
```

Alternatively, enter `http://127.0.0.1:8002/docs` directly into your browser's address bar. A URL by itself is **not** a PowerShell command.

## 2. Try it in Swagger without writing code

The Swagger page at `http://127.0.0.1:8002/docs` exposes three endpoints:

| Endpoint | Purpose | Input |
| --- | --- | --- |
| `POST /api/v1/summarization/text` | Summarize Persian text pasted directly into a request | JSON: `text` and `summary_length` |
| `POST /api/v1/summarization/file` | Summarize **one document** | One uploaded file and an optional length |
| `POST /api/v1/summarization/files` | Summarize **several documents independently** | Multiple uploaded files and an optional length |

### Summarize text

1. Expand `POST /api/v1/summarization/text` and select **Try it out**.
2. Paste this request into **Request body**.
3. Click **Execute** and inspect **Response body**.

```json
{
  "text": "سازمان هواشناسی اعلام کرد که بارش باران در روزهای آینده در مناطق شمالی کشور افزایش می‌یابد. کارشناسان توصیه کردند رانندگان پیش از سفر وضعیت جاده‌ها را بررسی کنند و به هشدارهای هواشناسی توجه داشته باشند.",
  "summary_length": "medium"
}
```

For a successful request, expect HTTP `200` and a `summary` field containing the generated Persian text. There is **no single predetermined summary** for this sample.

### Upload one PDF, Word, or TXT file

1. Expand `POST /api/v1/summarization/file` and select **Try it out**.
2. Use **Choose File** under `file` to select a `TXT`, text-based `PDF`, or `DOCX` document.
3. Set `summary_length` to `medium` and click **Execute**.
4. Inspect the `summary` and `success: true` fields in the response.

A **text-based PDF** contains selectable/extractable text. An image-only scanned PDF is **not supported**, because OCR is outside this MVP.

### Upload multiple files

Open `POST /api/v1/summarization/files`, choose several files, and click **Execute**. The result includes `results`, `succeeded`, and `failed`. **Each file receives its own result**; this endpoint does **not** merge all documents into one combined summary.

Even with HTTP `200`, individual items can have `success: false`. Always inspect each result.

## 3. Summary length: short, medium, long

The optional `summary_length` field defaults to `medium`:

| Value | Maximum generated tokens per model call |
| --- | ---: |
| `short` | 40 |
| `medium` | 80 |
| `long` | 120 |

These are **upper bounds, not word counts or guaranteed output lengths**. Generation may end earlier, producing the same summary for different values.

For example, a user tested an **eight-page PDF with 18,052 extracted characters**. Both `medium` and `long` returned the **same 113-character summary**. Therefore, choosing `long` does not necessarily solve under-summarization of long documents.

## 4. Call the REST API directly

The Docker base URL used here is `http://127.0.0.1:8002`.

### PowerShell: summarize Persian text

```powershell
$body = @{
    text = 'سازمان هواشناسی از افزایش بارش باران در شمال کشور خبر داد و به رانندگان هشدار داد.'
    summary_length = 'medium'
} | ConvertTo-Json -Compress

Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8002/api/v1/summarization/text' -ContentType 'application/json; charset=utf-8' -Body ([System.Text.Encoding]::UTF8.GetBytes($body))
```

### PowerShell: upload one file

Replace `sample.pdf` with the path to a **real file** on your machine:

```powershell
curl.exe -F 'file=@sample.pdf;type=application/pdf' -F 'summary_length=medium' http://127.0.0.1:8002/api/v1/summarization/file
```

### PowerShell: upload multiple files

Both sample files must exist in the current directory or be referenced by their full paths:

```powershell
curl.exe -F 'files=@sample.txt;type=text/plain' -F 'files=@sample.docx;type=application/vnd.openxmlformats-officedocument.wordprocessingml.document' -F 'summary_length=long' http://127.0.0.1:8002/api/v1/summarization/files
```

When using `curl -F`, **do not set the multipart `Content-Type` header manually**. Curl automatically includes the necessary boundary.

### Linux/macOS: curl examples

After starting the Docker container with the same port mapping:

```bash
curl --fail-with-body -H 'Content-Type: application/json; charset=utf-8' \
  -d '{"text":"بارندگی در شمال کشور افزایش می‌یابد و رانندگان باید به هشدارهای جاده‌ای توجه کنند.","summary_length":"medium"}' \
  http://127.0.0.1:8002/api/v1/summarization/text

curl --fail-with-body -F 'file=@sample.txt;type=text/plain' -F 'summary_length=medium' \
  http://127.0.0.1:8002/api/v1/summarization/file
```

### Understand the responses

- `/text` returns `summary`, `summary_length`, `input_characters`, and `output_characters`.
- `/file` additionally returns `filename`, `success`, `error_code`, and `error_message`.
- `/files` returns a `results` array plus `succeeded` and `failed` counts.
- `input_characters` is the length of the source text after extraction; `output_characters` is the length of the generated summary. **Neither measures factual accuracy.**

## 5. About the model and processing pipeline

- **Checkpoint:** [`nafisehNik/mt5-persian-summary`](https://huggingface.co/nafisehNik/mt5-persian-summary), pinned to revision `b575560ad967050e77a40f907abb1ebbeefb9a15`. It belongs to the **mT5 encoder-decoder Transformer** family and is described by its publisher as fine-tuned for Persian news summarization.
- **Not a training repository:** This project does not train mT5 from scratch or perform additional fine-tuning. It integrates an existing checkpoint into a FastAPI service. The FP32 weights are approximately **1.2 GB**; the frequently cited **~300 million parameters** is an estimate, not a verified parameter count.
- **Processing pipeline:** `HTTP request → Text extraction (for files) → Token-aware chunking → Hierarchical summarization (for long inputs) → mT5 inference → JSON response`.
- **Long documents:** Text is divided into token-aware chunks; intermediate summaries are combined and may be summarized again. Extremely large inputs can still hit explicit processing budgets and fail rather than silently processing without limits.
- **Runtime:** The model loads lazily, once per process. The supplied Docker image uses **CPU inference and one Uvicorn worker**.
- **Tokenization and decoding:** SentencePiece and Hugging Face Transformers. Current generation settings include `num_beams=2`, `do_sample=False`, `early_stopping=True` and a limit of **1,000 input tokens per model chunk**.
- **Licensing:** The model card declares **MIT** for the model; downstream training-data rights should be reviewed separately. The repository's own code redistribution rights require separate verification: **there is no root `LICENSE` file in the currently checked revision**.

Source of truth for configuration: `src/host/res/appsettings.yaml` and `src/host/res/appsettings.development.yaml`. Settings are YAML-backed; do not assume arbitrary environment keys such as `MODEL_ID` are implemented.

## 6. Run from source (developers)

If you want to modify or develop the service rather than use its Docker image, clone the repository and create a virtual environment.

**Windows PowerShell / Python 3.12:**

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
python -m uvicorn src.host.app:app --host 127.0.0.1 --port 8001 --workers 1
```

**Linux/macOS:**

```bash
git clone https://github.com/Amirmahdimtz/mT5-Persian-Summary.git
cd mT5-Persian-Summary
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip check
export env_type=development
python -m uvicorn src.host.app:app --host 127.0.0.1 --port 8001 --workers 1
```

On Linux CPU hosts, installing PyTorch separately from the official CPU index (as done in the Dockerfile) may be appropriate. On macOS, install a compatible PyTorch distribution for your platform. When running from source, Swagger is at `http://127.0.0.1:8001/docs`, **not** the Docker example's port `8002`.

**Optional Docker Compose** (performs a local image build):

```powershell
docker compose up --build -d
docker compose ps
docker compose logs --tail 100 summarizer
docker compose down
```

The project's `compose.yaml` publishes host port **8000** and uses its own `hf_cache` volume, separate from the `mt5_hf_cache` volume above. Compose runtime has **not been independently verified**. Downloading the Linux PyTorch wheel from its CDN can fail on slow/unreliable networks; prefer the **prebuilt GHCR image** for an initial trial. The workflow at `.github/workflows/docker-image.yml` is **manually dispatched**, not triggered by every push.

## 7. Limits, errors, and troubleshooting

| Limit | Current behavior |
| --- | --- |
| Direct text | **1–200,000 Unicode characters**, with nonblank content required |
| Individual file | Up to **20 MiB** |
| Multi-file upload | **1–32 files**, with a default **32 MiB aggregate** file-byte budget |
| Formats | UTF-8 TXT, text-extractable PDF, DOCX |
| PDF processing | No OCR for image-only scans; unreadable, corrupt, or encrypted documents may be rejected |
| Model concurrency | **One concurrent inference per worker**; the default admission queue wait is **30 seconds** |
| Health check | HTTP liveness only, **not model readiness** |
| Uploaded document storage | No permanent application-level storage of uploads; temporary buffers/files may be used while processing |

| HTTP code | Typical meaning |
| --- | --- |
| `200` | Request processed; for batches, also inspect `success` on every file |
| `400` | Invalid/empty filename, empty upload, or malformed upload |
| `408` | Multipart upload stalled beyond the configured idle timeout |
| `413` | Upload size, document count, or processing budget exceeded |
| `415` | Unsupported extension or incompatible MIME type |
| `422` | Invalid text, `summary_length`, or unreadable/unprocessable file |
| `500` | Internal parsing or inference failure |
| `503` | Model unavailable or request admission saturated |

**Common problems:**

- **Swagger does not open:** Run `docker ps -a --filter name=mt5-persian-summary`. If stopped, use `docker start mt5-persian-summary`. During startup the health status can say `starting`; try the health check again after initialization. Open the URL in a browser, not as a bare PowerShell command.
- **`docker pull` returns `denied`:** Check that the GHCR package/tag exists. A private package may require login with a token permitted to `read:packages`. Never commit tokens to source control or paste them into issue logs.
- **First inference is slow or returns `503`:** Check Hugging Face connectivity, free cache space, available RAM, and `docker logs --tail 100 mt5-persian-summary`. Resolve the underlying loading issue and restart if necessary.
- **Summary is too short, incomplete, or identical across tiers:** Healthy HTTP does not prove summary quality. Compare important topics, dates, numbers, named entities, and the direction of changes with the original. `long` only increases the token budget.
- **A colleague cannot open `localhost`:** `127.0.0.1` points to the local machine. The current MVP has **no public-facing authentication or rate limiting**. Do not expose it directly to the internet without an appropriately secured gateway and access controls.

In a prior quality check, the model omitted some topics from a multi-topic sample and reversed the reported direction of a pollution change. It should not be relied upon without human review for sensitive organizational, legal, medical, or financial documents. **Use confidential organizational documents only with the necessary permission.**

## 8. Tests, project structure, and delivery status

After installing `requirements.txt` and activating the Python virtual environment:

```powershell
python -m pip check
python -m compileall -q src tests
python -m pytest -q
```

Run the optional **real-model/live HTTP** end-to-end smoke test against an already running Docker container (requires the development dependencies on the host):

```powershell
python tests/e2e_http_smoke.py --base-url http://127.0.0.1:8002 --large-upload
```

**Last recorded verification (October 25, 2026):** On Windows, **266 tests passed with two non-failing deprecation warnings**. The GHCR image was pulled, the container remained `healthy` for over 51 minutes, `GET /api/v1/health` returned `200`, and live HTTP checks passed for text, synthetic text-layer PDF, TXT, DOCX, multi-file summarization, and expected negative upload cases. **These results are not a summary-factuality benchmark, load test, or production security certification.** Docker Compose execution, peak memory measurement, and graceful shutdown under active inference were not independently tested.

```text
src/
  host/                    # FastAPI startup and YAML settings
  application/             # HTTP controllers, DTOs and upload validation
  core/services/           # Extraction, chunking and summarization logic
  infrastructure/          # Dependency injection and mT5 model provider
tests/                     # Unit, integration and opt-in live HTTP smoke tests
docs/                      # Architecture, model verification and progress
Dockerfile
compose.yaml
requirements.txt
```

More technical details: [Implementation progress](docs/IMPLEMENTATION_PROGRESS.md), [model verification](docs/STAGE2_MODEL_VERIFICATION.md), [architecture guide (Persian)](Service_Architecture_Guide_FA.md), and [implementation plan](IMPLEMENTATION_PLAN.md).

**Project status:** All eight MVP implementation stages are marked **Completed**. OCR, a dedicated UI, database, authentication, background job queue, fine-tuning, and guaranteed factual accuracy are **not part of this version**.

**Stop or restart the Docker container when needed:**

```powershell
docker stop mt5-persian-summary
docker start mt5-persian-summary
```
