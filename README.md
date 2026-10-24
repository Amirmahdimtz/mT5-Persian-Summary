# mT5 Persian Summarization Service

Stage 1 provides a runnable FastAPI application, configuration reader, convention-based constructor dependency injection, controller auto discovery, and a health check. Stage 2 adds a lazy ML provider but still does **not** expose summarization endpoints.

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
