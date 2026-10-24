# mT5 Persian Summarization Service

Stages 1–5 provide the FastAPI/DI foundation, lazy mT5 provider, document extraction and summarization orchestration. Stage 6 exposes the REST API for Persian text and documents.

## Requirements

- Python 3.11 or newer
- pip

## Setup

Clone the repository and run the following commands from the repository root.

### Linux / macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
export env_type=development
python -m pytest -q
python -m src.host.app
```

### Windows PowerShell

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:env_type = "development"
python -m pytest -q
python -m src.host.app
```

If your Windows installation does not provide Python 3.11, use an installed Python 3.11+ interpreter to create the virtual environment.

The development configuration is in `src/host/res/appsettings.development.yaml`. When `env_type=development` (the default), this file is used. Any other `env_type` selects `src/host/res/appsettings.yaml`. Both contain `app.name`, `app.version`, `server.host`, `server.port`, and `api.prefix`. `ENV_TYPE` is also accepted if `env_type` is not set. Environment selection happens at application startup.

## Verify

With the service running with its default configuration:

```bash
curl -i http://127.0.0.1:8000/api/v1/health
```

Expected: HTTP `200 OK` and `{"status":"ok"}`.

Swagger UI: http://127.0.0.1:8000/docs

OpenAPI JSON: http://127.0.0.1:8000/openapi.json

The host and port used by `python -m src.host.app` are read from the selected YAML settings. If you customize `api.prefix` or the host/port, adapt the URLs above.

## Architecture

- `src/host/app.py`: bootstrap and ASGI entry point
- `src/application/web.py`: controller discovery and FastAPI setup
- `src/application/health/health_controller.py`: health endpoint
- `src/core/services/`: reserved for future business services
- `src/infrastructure/di/`: `@inject`, reflection and bootstrap
- `src/infrastructure/utils/config_reader.py`: singleton YAML configuration provider
- `docs/IMPLEMENTATION_PROGRESS.md`: stage status and test results

Only classes decorated with `@inject` are registered during bootstrap. Providers are scanned from infrastructure, core, and application, in that order. Controllers are independently auto-discovered from direct feature folders in `src/application/`. Missing or invalid providers/controllers cause startup errors rather than silently dropping features. Singleton lifetime is per Python process; `ConfigReader` is a singleton when resolved through DI.

## Testing

```bash
python -m compileall -q src tests
python -m pytest -q
```

The Stage 1 tests do not require model downloads, network access, a database, or credentials.


## Windows troubleshooting

If Python 3.11 is not installed but Python 3.12 is, use `py -3.12 -m venv .venv`. Python 3.11 or newer is supported.

If PowerShell blocks `Activate.ps1`, enable local script execution for **only this PowerShell process**:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\.venv\Scripts\Activate.ps1
```

Alternatively, do not activate the environment and invoke `.\.venv\Scripts\python.exe` for every Python command.

If port 8000 is already occupied (Windows error 10048), keep the existing process undisturbed and run the ASGI app on another port:

```powershell
python -m uvicorn src.host.app:app --host 127.0.0.1 --port 8001
Invoke-RestMethod http://127.0.0.1:8001/api/v1/health
```

Use two terminal windows if running the server in the foreground: the second command belongs in a separate PowerShell session.


## Stage 2: mT5 model provider (CPU-first)

Stage 2 includes a lazy, DI-resolvable infrastructure-only model provider. It does not add summarization HTTP endpoints. The model is downloaded only during the first valid call to summarize or summarize_async; startup and health checks do not download it. The model is loaded once per process; failed initialization is cached until process restart.

### Windows PowerShell setup and verification (Python 3.12)

From the repository root:

~~~powershell
git pull --ff-only origin main
if (!(Test-Path .venv)) { py -3.12 -m venv .venv }
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install "torch>=2.6,<3.0" --index-url https://download.pytorch.org/whl/cpu
python -m pip install -r requirements.txt
$env:env_type = "development"
python -c "from src.infrastructure.utils.config_reader import ConfigReader; print(ConfigReader().get('model'))"
python -m compileall -q src tests
python -m pytest -q
python -m src.infrastructure.ml.smoke_mt5_model
~~~

The smoke command downloads approximately 1.2 GB of weights (unless already cached), generates a summary from a short Persian text, asserts a non-empty summary, and prints it. **It is intentionally not collected by normal pytest.** Ensure several GB of free disk and at least 8 GB free RAM for initial CPU evaluation (estimate, unmeasured). A real successful result has not yet been verified.

Inspect the Hugging Face cache, if HF_HOME is not overridden:

~~~powershell
Get-ChildItem (Join-Path $env:USERPROFILE '.cache\huggingface\hub') -Directory -Filter 'models--nafisehNik--mt5-persian-summary'
~~~

For the FastAPI liveness regression (separate PowerShell window for the request):

~~~powershell
python -m uvicorn src.host.app:app --host 127.0.0.1 --port 8001
Invoke-RestMethod http://127.0.0.1:8001/api/v1/health
~~~

Expected health JSON is {"status":"ok"}; Swagger is at http://127.0.0.1:8001/docs. Model metadata, revision, licensing and security considerations are in docs/STAGE2_MODEL_VERIFICATION.md. On Windows, if PowerShell blocks venv activation, run Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned and retry. Never commit model cache or tokens.

## Stage 3: In-memory document extraction

`DocumentExtractionService` is a Python service (not an HTTP endpoint). It
accepts `bytes` and a filename, dispatches by the case-insensitive suffix
`.txt`, `.pdf` or `.docx`, and returns normalized Unicode text. It does not
call mT5, store documents, or create temporary files.

```python
from pathlib import Path
from src.core.services.summarization.document_extraction_service import DocumentExtractionService

path = Path("your-document.pdf")
text = DocumentExtractionService().extract(path.read_bytes(), path.name)
print(text)
```

TXT requires UTF-8 with or without a BOM; invalid UTF-8 or binary control
characters fail explicitly. PDF extraction uses pypdf's layout mode with
conservative Persian RTL visual-order recovery: some PDF generators store
visually ordered glyphs, while others already provide logical-order Unicode.
The extractor compares common Persian word patterns line by line and avoids
blindly reversing all text. Numbers and standalone Latin tokens are preserved
in the tested cases. This is a heuristic, **not a universal guarantee** for
mixed-direction layouts or PDFs with broken font mappings. Page order and
rotated text are retained. Image-only/empty PDFs return `NoExtractableTextError`,
not OCR. Encrypted PDFs return `PasswordProtectedPdfError`. DOCX extraction
uses python-docx 1.2's `iter_inner_content()` for document-order paragraphs
and tables, including nested tables. Legacy `.doc` is unsupported. Headers,
footers, comments, text boxes, tracked changes, and embedded objects are not
guaranteed to be extracted.

Normalization: convert CRLF/CR to LF and trim document-edge whitespace;
preserve internal blank lines, Persian/Arabic letters, zero-width non-joiners,
punctuation, and numbers. Rejected input raises named, non-HTTP exceptions
defined in the service module. Resource budgets: 20 MiB source, 5 million
extracted characters, 500 PDF pages, 2,000 DOCX ZIP members, 20 MiB per
uncompressed ZIP member and 80 MiB expanded DOCX total. **These are
post-upload extraction guards**, not replacements for request-stream limits
in Stage 6/7. PDFs with incomplete or incorrect Unicode maps may yield
incorrect text and still require review with real Persian documents.

To run the standalone real-parser integration smoke tests from the repository
root, without an HTTP server or a model download:

```bash
python -m pytest -q -s tests/test_document_extraction_service.py -k smoke_
```

Expected: three passing TXT, PDF and DOCX smoke cases printing Persian text.
The PDF sample has a generated Unicode ToUnicode map rather than a real
embedded Persian font; this checks the parser contract but cannot establish
accuracy across arbitrary third-party PDFs.

For the full checks run `python -m compileall -q src tests` and
`python -m pytest -q`. The previously reported Windows/Python 3.12.10
regression had 88 passed tests before this RTL recovery fix; rerun it after
pulling the latest changes. Validate the text order against a representative
real Persian PDF; see `docs/IMPLEMENTATION_PROGRESS.md`.


## Stage 4: Token-aware chunking and bounded hierarchical summaries

Stage 4 implements TextChunkingService and LongTextSummarizationService
without new HTTP endpoints, persistence, third-party dependencies or changes
to the extractors. Both use @inject and constructor DI. Resolve services
after bootstrap_di() rather than creating dependencies manually:

~~~python
import asyncio
from src.infrastructure.di.bootstrap import bootstrap_di
from src.infrastructure.di.inject import resolve
from src.core.services.summarization.long_text_summarization_service import LongTextSummarizationService

bootstrap_di()
service = resolve(LongTextSummarizationService)
summary = asyncio.run(service.summarize_async("متن فارسی برای خلاصه سازی", "medium"))
print(summary)
~~~

### Input and resource limits

- A model call must meet **both limits**: at most **1,000 encoded input
  tokens including tokenizer-added specials**, and **20,000 characters**
  under current configuration. These are configured inference safeguards,
  not the measured network context capacity. No task prefix is used.
  Counting through the pinned tokenizer initializes tokenizer assets only,
  not the approximately 1.2 GB model weights.
- Chunking folds CRLF/CR to LF, collapses horizontal whitespace runs,
  reduces 3+ consecutive newlines to two, and strips document edges.
  Every character of the **normalized** text appears in source order
  across chunks. Original indentation/spaces are not byte-preserved.
  Paragraph, line, sentence and word boundaries are preferred; a long
  unpunctuated word can be split at a character boundary if necessary.
  Every resulting chunk is validated with the exact mT5 tokenizer.
- Operational budgets: **200,000 normalized source characters**,
  **64 chunks**, **6 hierarchy levels** and **128 model calls**. These
  conservative bounds are CPU service limits, not model specifications.
  A level summarizes chunks sequentially, joins summaries in source
  order and continues until one valid final-model input is available.
  No sufficient reduction (at least 5% fewer characters), exhausted
  work budget, empty output, or excessive final output yields an explicit
  typed error rather than a truncated or partial answer.
- Generation budgets for short, medium, long are **ceil(1/3)**,
  **ceil(2/3)** and **100%** of configured model.max_output_tokens:
  currently **40**, **80**, **120**. This bound is the Transformers
  generation max_length (decoder sequence tokens, including specials),
  **not a word or character count**. The final decoded/re-encoded output
  is independently checked against the requested token budget and
  rejected if it exceeds it.
- summarize_async and worker-thread tokenization/chunking do not block
  the ASGI event loop while executing inference. The provider retains a
  per-process, sequential inference lock and one model instance. Task
  cancellation does not forcibly interrupt a running model call in
  a worker thread; no partial output is returned.

Hierarchical summarization may discard more semantic detail than a
single model pass. Chunking guarantees normalized source coverage **before**
summarization, not preservation of every original fact in the result.

### Stage 4 tests and optional real-model smoke

Unit tests rely on fake tokenizers/providers and **never download weights**:

~~~powershell
$env:env_type = "development"
python -m compileall -q src tests
python -m pytest -q tests/test_text_chunking_service.py tests/test_long_text_summarization_service.py tests/test_mt5_stage4_provider.py
python -m pytest -q
~~~

Explicit opt-in real CPU smoke:

~~~powershell
python -m src.infrastructure.ml.smoke_mt5_long_text
~~~

The smoke uses generated Persian text and multiple potentially slow
model inferences. Weights are reused from the Hugging Face cache if
present; otherwise the pinned checkpoint downloads. Allow several GB
free disk space and approximately 8 GB available RAM as an unmeasured
CPU planning estimate. Keep this smoke outside the default pytest suite.
It checks the final summary is nonempty and within the encoded-token
output budget. Local isolated Stage 4 mock tests are not a substitute
for the full Windows/Python 3.12.10 regression and real-model smoke.


## Stage 5: Main Python summarization service

Stage 5 adds SummarizationService as an in-process Python orchestration layer.
It does not create HTTP summarization endpoints (these belong to Stage 6).
Resolve it after bootstrap_di() so the existing extractor and hierarchical
summarizer are constructor-injected, rather than loading model weights directly:

~~~python
import asyncio
from src.infrastructure.di.bootstrap import bootstrap_di
from src.infrastructure.di.inject import resolve
from src.core.services.summarization.summarization_service import (
    DocumentInput, SummarizationService,
)

bootstrap_di()
service = resolve(SummarizationService)

async def example():
    text = await service.summarize_text_async("یک متن فارسی مناسب برای خلاصه سازی", "medium")
    one_file = await service.summarize_file_async(
        "متن فارسی سند".encode("utf-8"), "example.txt", "short"
    )
    multiple = await service.summarize_files_async([
        DocumentInput("first.txt", "متن اول".encode("utf-8")),
        DocumentInput("second.txt", "متن دوم".encode("utf-8")),
    ], "medium")
    return text, one_file, multiple

text_result, file_result, batch_result = asyncio.run(example())
print(text_result.summary, file_result.summary)
for item in batch_result.results:
    print(item.filename, item.success, item.summary, item.error_code)
~~~

The example runs real model inference on the first call; weights may need to
be downloaded and CPU execution can be slow. Tests use fake dependencies.

Public contracts:
- summarize_text_async(text: str, summary_length: str = "medium") returns
  TextSummaryResult(summary, summary_length, input_characters, output_characters).
- summarize_file_async(content: bytes, filename: str,
  summary_length: str = "medium") returns a successful FileSummaryResult,
  or raises the existing typed extraction/model/hierarchy exception.
- summarize_files_async(files: Sequence[DocumentInput],
  summary_length: str = "medium") returns MultiFileSummaryResult with ordered
  FileSummaryResult entries and computed succeeded/failed counts.
- DocumentInput is an immutable dataclass of filename and content bytes.
  FileSummaryResult has success, summary, summary_length, filename,
  input_characters, output_characters, error_code and error_message.
  Failure entries have success=False, summary=None, error_code set to the
  known exception type, and a deliberately generic error_message.

Validation of the summary length and the batch collection is request-wide;
invalid file input is handled per document after the collection is accepted.
Files run sequentially with a maximum of 32 documents per batch, preserving
order and duplicate names by index and without unbounded task spawning.
Document extraction is offloaded with asyncio.to_thread; the Stage 4 service
already offloads tokenizer/chunking and inference. Recognized document,
parser, chunking and model errors yield file failures without dropping other
results; unexpected code defects and cancellation propagate. Worker-thread
extraction/inference may finish in the background after cancellation of an
awaiting coroutine (they cannot be forcibly interrupted).

Input/output character counts are counts of Python Unicode characters
(Unicode code points) in the supplied/extracted text and returned summary,
not word counts, encoded token counts, or chunk counts. Stage 5 does not
guess tokens, chunks, or model IDs or load weights to calculate metadata.
Existing per-document extraction guards, 200,000 normalized character
hierarchy work budget, 64 chunk limit, six hierarchy levels and 128 model
calls remain unchanged. Callers must apply upload-size limits while reading
streams in Stage 6/7, before passing any bytes to this service. PDFs without
extractable text remain unsupported; OCR is not provided.

## Stage 6: Summarization REST API and upload safety

All routes use the configured `api.prefix` (default `/api/v1`); Swagger is at `/docs` and OpenAPI JSON at `/openapi.json`. Controller discovery and constructor `@inject` connect the HTTP layer to the existing `SummarizationService`; no model weights load during startup. Model inference happens only for processable documents.

| Method | Route | Body | Success |
|---|---|---|---|
| POST | `/api/v1/summarization/text` | JSON `text`, optional `summary_length` | 200: `summary`, `summary_length`, `input_characters`, `output_characters` |
| POST | `/api/v1/summarization/file` | multipart `file`, optional `summary_length` | 200: `filename`, `summary_length`, `success`, `summary`, character counts, nullable errors |
| POST | `/api/v1/summarization/files` | repeated multipart `files`, optional `summary_length` | 200: ordered `results` with `succeeded` and `failed` |

`summary_length` is exactly `short`, `medium` (default) or `long`.
`text` must be a nonempty string, not just whitespace, at most 200,000 characters.
TXT requires UTF-8 (optional BOM); only text-based PDFs and DOCX are supported, not OCR.
Valid upload media types match the file extension, or may be `application/octet-stream` or absent. Filenames must be safe basenames, up to 255 characters.

**Resource policy:** 20 MiB per file (the existing extraction limit); 1–32 files per batch (the existing Core limit); configurable **32 MiB aggregate file bytes per request** via `api.upload.max_total_bytes` in both appsettings YAML files (integer 20–64 MiB, default 33554432). File content is read in at most 64 KiB per call and bounded by both limits. An ASGI middleware first caps the entire multipart wire body at aggregate budget plus 1 MiB framing allowance **without trusting Content-Length**. To return HTTP 413 before multipart parsing, it spools at most 1 MiB in RAM and the remaining permitted raw body into an automatically closed temporary spool file; Starlette's `UploadFile` separately uses spooling and may also touch temporary disk. Files are never stored permanently by application code. Source bytes are held in RAM for Stage 5's existing in-memory `DocumentInput` contract; the per-request aggregate budget makes that predictable. This is not a reverse-proxy-wide connection or concurrency limit; Stage 7 will revisit multi-request admission and memory profiling.

**Error contract:** for application errors, `{"detail":{"code":"...","message":"..."}}`, with fixed sanitized messages (no parser/model exception strings or document bodies). `400`: invalid filename, empty upload or malformed multipart; `413`: request/per-file/aggregate/processing limit; `415`: unsupported extension or media type; `422`: invalid JSON, missing fields, invalid text/length or corrupted/unextractable document; `500`: model inference failure, empty output or unexpected service result; `503`: model initialization unavailable. Unexpected programming exceptions propagate to the framework, not disguised as known document errors. For multipart collection-level validation failure, no inference is attempted. For a valid batch, every document has an independent `success`, `error_code` and safe `error_message`; ordered results keep duplicate filenames and partial/all-file failures return **HTTP 200**. Only successful items contain a non-null summary and counts.

Example JSON request and response (illustrative schema, not a live model result):

```json
{"text":"این یک متن فارسی برای خلاصه‌سازی است.","summary_length":"short"}
```

```json
{"summary":"خلاصه فارسی","summary_length":"short","input_characters":37,"output_characters":11}
```

The counts above are illustrative; actual counts are computed by the Core service from the actual input and generated summary. Successful single-file response follows this structure:

```json
{"filename":"sample.txt","summary_length":"medium","success":true,"summary":"خلاصه فارسی","input_characters":100,"output_characters":11,"error_code":null,"error_message":null}
```

Failed item in a valid multi-file response:

```json
{"filename":"bad.pdf","summary_length":"medium","success":false,"summary":null,"input_characters":null,"output_characters":null,"error_code":"InvalidDocumentError","error_message":"Document could not be summarized; see error_code."}
```

### Stage 6 Windows PowerShell verification

Open PowerShell in the repository, not in a different project's virtual environment:

```powershell
Set-Location -LiteralPath 'E:\\Amirmahdi_mtz\\Military Service\\mT5-Persian-Summary'
git pull --ff-only origin main
git rev-parse HEAD
git status --short
if (!(Test-Path -LiteralPath '.venv\\Scripts\\python.exe')) { py -3.12 -m venv .venv }
& '.\\.venv\\Scripts\\Activate.ps1'
$env:env_type = 'development'
python --version
python -m pip install -r requirements.txt
python -m pip check
python -m compileall -q src tests
python -c "from src.infrastructure.di.bootstrap import bootstrap_di; from src.infrastructure.di.inject import resolve; from src.application.summarization.summarization_controller import SummarizationController; from src.core.services.summarization.summarization_service import SummarizationService; bootstrap_di(); assert resolve(SummarizationController); assert resolve(SummarizationService); print('DI OK')"
python -m pytest -q tests/test_summarization_api.py
python -m pytest -q
python -m pytest -q -s tests/test_document_extraction_service.py -k smoke_
python -m uvicorn src.host.app:app --host 127.0.0.1 --port 8001
```

In a second PowerShell window, with the service running:

```powershell
$base = 'http://127.0.0.1:8001'
Invoke-RestMethod "$base/api/v1/health"
Invoke-RestMethod "$base/openapi.json" | Select-Object -ExpandProperty paths
Start-Process "$base/docs"
$body = @{ text='این یک متن فارسی برای خلاصه‌سازی است.'; summary_length='short' } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "$base/api/v1/summarization/text" -ContentType 'application/json; charset=utf-8' -Body ([System.Text.Encoding]::UTF8.GetBytes($body))
Set-Content -LiteralPath '.\\sample.txt' -Value 'این یک نمونه متن فارسی برای خلاصه سازی است.' -Encoding utf8
Set-Content -LiteralPath '.\\invalid.pdf' -Value 'not a PDF' -Encoding ascii
curl.exe -sS -i -X POST "$base/api/v1/summarization/file" -F "file=@sample.txt;type=text/plain" -F "summary_length=medium"
curl.exe -sS -i -X POST "$base/api/v1/summarization/files" -F "files=@sample.txt;type=text/plain" -F "files=@invalid.pdf;type=application/pdf" -F "summary_length=short"
curl.exe -sS -i -X POST "$base/api/v1/summarization/file" -F "file=@invalid.pdf;type=application/pdf"
```

Expected: `GET /health` returns HTTP 200 with `{"status":"ok"}`; Swagger and OpenAPI expose the three POST routes; text and valid TXT return HTTP 200 with typed summaries when the real model succeeds; a corrupt single PDF returns 422; a valid multipart batch returns HTTP 200 with one result per input position, even if some/all files fail. Real-model output quality is not guaranteed; a prior smoke produced only `.`. Delete `sample.txt` and `invalid.pdf` when finished.

Stage 6 HTTP tests use fake Core services and do not download mT5 weights. A real model/API smoke is optional and separate from pytest regression.
