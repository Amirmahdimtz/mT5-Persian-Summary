# syntax=docker/dockerfile:1
# CPU-only runtime; this image does not bundle Hugging Face model weights.
FROM python:3.12.10-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    env_type=production \
    HF_HOME=/home/app/.cache/huggingface \
    HF_HUB_DISABLE_TELEMETRY=1

WORKDIR /app

# Install CPU-only PyTorch first to avoid accidentally resolving CUDA wheels.
# Keep the dependency layer independent of application source changes.
COPY requirements.txt ./requirements.txt
# A longer socket timeout handles large CPU wheels on slower connections.
# BuildKit's pip cache survives rebuilds without becoming part of the image.
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install --timeout 180 --retries 8 'torch>=2.6,<3.0' \
        --index-url https://download.pytorch.org/whl/cpu \
    && python -m pip install --timeout 180 --retries 8 -r requirements.txt \
    && python -m pip check

RUN useradd --uid 10001 --create-home --shell /usr/sbin/nologin app \
    && mkdir -p /home/app/.cache/huggingface \
    && chown -R app:app /home/app

COPY --chown=app:app src/ ./src/
USER app
EXPOSE 8000

# This is HTTP/process liveness only; model weights load lazily on inference.
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=3).close()" || exit 1

# Exec-form PID 1 receives SIGTERM. One worker avoids duplicated mT5 weights.
CMD ["python", "-m", "uvicorn", "src.host.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
