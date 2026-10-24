"""Pre-multipart ASGI upload budget, independent of untrusted Content-Length."""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable
from tempfile import SpooledTemporaryFile
from typing import Any

from starlette.responses import JSONResponse

from src.infrastructure.utils.config_reader import ConfigReader, ConfigurationError

# Allow framing and form fields independently of the summed file-byte budget.
MULTIPART_OVERHEAD_BYTES = 1024 * 1024
MAX_CONFIGURED_UPLOAD_BYTES = 64 * 1024 * 1024
ASGI_REPLAY_CHUNK_BYTES = 64 * 1024
ASGI_MEMORY_SPOOL_BYTES = 1024 * 1024


def configured_upload_budget(config_reader: ConfigReader) -> int:
    budget = config_reader.get("api.upload.max_total_bytes")
    if type(budget) is not int or not 20 * 1024 * 1024 <= budget <= MAX_CONFIGURED_UPLOAD_BYTES:
        raise ConfigurationError("api.upload.max_total_bytes must be between 20 and 64 MiB")
    return budget


def configured_upload_runtime(config_reader: ConfigReader) -> tuple[int, float]:
    active = config_reader.get("api.upload.max_active_requests")
    idle = config_reader.get("api.upload.idle_timeout_seconds")
    if type(active) is not int or not 1 <= active <= 16:
        raise ConfigurationError("api.upload.max_active_requests must be in [1, 16]")
    if type(idle) not in (int, float) or not 1 <= idle <= 300:
        raise ConfigurationError("api.upload.idle_timeout_seconds must be in [1, 300]")
    return active, float(idle)


class UploadBodyLimitMiddleware:
    """Cap raw body before Starlette parses/spools multipart files.

    A bounded ASGI spool (1 MiB in RAM, remainder in temporary storage) is
    necessary because FastAPI converts exceptions thrown by its form-body
    receiver into HTTP 400, preventing an accurate HTTP 413 response. The
    spool is always closed, including cancellation and validation errors.
    """

    def __init__(
        self,
        app: Any,
        *,
        api_prefix: str,
        max_total_bytes: int,
        max_active_requests: int = 2,
        idle_timeout_seconds: float = 30.0,
        admission_wait_seconds: float = 0.25,
    ) -> None:
        if type(max_active_requests) is not int or max_active_requests < 1:
            raise ValueError("max_active_requests must be positive")
        if idle_timeout_seconds <= 0 or admission_wait_seconds <= 0:
            raise ValueError("upload timeouts must be positive")
        self.app = app
        self._active = threading.BoundedSemaphore(max_active_requests)
        self._idle_timeout_seconds = idle_timeout_seconds
        self._admission_wait_seconds = admission_wait_seconds
        self._paths = {
            f"{api_prefix}/summarization/file",
            f"{api_prefix}/summarization/files",
        }
        self._body_budget = max_total_bytes + MULTIPART_OVERHEAD_BYTES

    async def __call__(self, scope: dict, receive: Callable, send: Callable) -> None:
        if (scope["type"] != "http" or scope.get("method") != "POST"
                or scope.get("path") not in self._paths):
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        media_type = headers.get(b"content-type", b"").split(b";", 1)[0].strip().lower()
        if media_type != b"multipart/form-data":
            await JSONResponse(
                status_code=415,
                content={"detail": {
                    "code": "UnsupportedMediaType",
                    "message": "Endpoint requires multipart/form-data.",
                }},
            )(scope, receive, send)
            return

        # The admission capacity is process-wide, including multiple ASGI
        # event loops; non-blocking polling never parks a worker thread.
        loop = asyncio.get_running_loop()
        deadline = loop.time() + self._admission_wait_seconds
        while not self._active.acquire(blocking=False):
            remaining = deadline - loop.time()
            if remaining <= 0:
                await JSONResponse(
                    status_code=503,
                    content={"detail": {
                        "code": "UploadCapacityExceeded",
                        "message": "Upload capacity is temporarily unavailable.",
                    }},
                )(scope, receive, send)
                return
            await asyncio.sleep(min(0.02, remaining))

        try:
            with SpooledTemporaryFile(max_size=ASGI_MEMORY_SPOOL_BYTES) as spool:
                total = 0
                while True:
                    try:
                        message = await asyncio.wait_for(
                            receive(), timeout=self._idle_timeout_seconds
                        )
                    except TimeoutError:
                        await JSONResponse(
                            status_code=408,
                            content={"detail": {
                                "code": "UploadReadTimeout",
                                "message": "Upload stream was idle for too long.",
                            }},
                        )(scope, receive, send)
                        return
                    if message["type"] != "http.request":
                        return  # Disconnected clients do not receive an HTTP response.
                    chunk = message.get("body", b"")
                    total += len(chunk)
                    if total > self._body_budget:
                        await JSONResponse(
                            status_code=413,
                            content={"detail": {
                                "code": "UploadBodyTooLarge",
                                "message": "Multipart request exceeds the configured upload budget.",
                            }},
                        )(scope, receive, send)
                        return
                    spool.write(chunk)
                    if not message.get("more_body", False):
                        break

                spool.seek(0)
                finished = False

                async def replay_receive() -> dict:
                    nonlocal finished
                    if not finished:
                        part = spool.read(ASGI_REPLAY_CHUNK_BYTES)
                        if part:
                            return {"type": "http.request", "body": part, "more_body": True}
                        finished = True
                        return {"type": "http.request", "body": b"", "more_body": False}
                    return await receive()

                await self.app(scope, replay_receive, send)
        finally:
            self._active.release()
