"""Stage 7 deterministic admission, cancellation and HTTP ingress tests.

No real mT5 model is downloaded by these tests.
"""

from __future__ import annotations

import asyncio
import threading

import pytest
from fastapi.testclient import TestClient
from starlette.responses import JSONResponse

from src.application.summarization.upload_limit_middleware import (
    UploadBodyLimitMiddleware,
    configured_upload_runtime,
)
from src.core.services.summarization.summarization_service import SummarizationService
from src.host.app import app
from src.infrastructure.ml.mt5_model_provider import ModelBusyError, Mt5ModelProvider
from src.infrastructure.utils.config_reader import ConfigReader, ConfigurationError


def _provider(**settings) -> Mt5ModelProvider:
    config = ConfigReader()
    config.get("model").update(settings)
    return Mt5ModelProvider(config)


def _scope() -> dict:
    return {
        "type": "http",
        "method": "POST",
        "path": "/api/v1/summarization/file",
        "headers": [(b"content-type", b"multipart/form-data; boundary=x")],
    }


def _body() -> dict:
    return {"type": "http.request", "body": b"x", "more_body": False}


@pytest.mark.parametrize("bad", [0, -1, True, 5, "1"])
def test_invalid_inference_capacity_rejected(bad):
    with pytest.raises(ConfigurationError, match="max_concurrent_inferences"):
        _provider(max_concurrent_inferences=bad)


@pytest.mark.parametrize("bad", [0, -1, True, float("nan"), 301])
def test_invalid_inference_wait_rejected(bad):
    with pytest.raises(ConfigurationError):
        _provider(queue_wait_seconds=bad)


def test_model_admission_timeout_does_not_start_second_worker(monkeypatch):
    provider = _provider(max_concurrent_inferences=1, queue_wait_seconds=0.05)
    entered = threading.Event()
    release = threading.Event()
    calls: list[str] = []

    def summarize(text, *, max_output_tokens=None):
        calls.append(text)
        entered.set()
        assert release.wait(3)
        return "خلاصه"

    monkeypatch.setattr(provider, "summarize", summarize)

    async def scenario():
        first = asyncio.create_task(provider.summarize_async("first"))
        try:
            assert await asyncio.to_thread(entered.wait, 1)
            with pytest.raises(ModelBusyError):
                await provider.summarize_async("second")
            assert calls == ["first"]
        finally:
            release.set()
        assert await asyncio.wait_for(first, 2) == "خلاصه"

    asyncio.run(scenario())


def test_cancelled_request_keeps_slot_until_real_thread_finishes(monkeypatch):
    provider = _provider(max_concurrent_inferences=1, queue_wait_seconds=2.0)
    entered = threading.Event()
    release = threading.Event()
    calls: list[str] = []

    def summarize(text, *, max_output_tokens=None):
        calls.append(text)
        if text == "first":
            entered.set()
            assert release.wait(3)
        return "خلاصه"

    monkeypatch.setattr(provider, "summarize", summarize)

    async def scenario():
        first = asyncio.create_task(provider.summarize_async("first"))
        assert await asyncio.to_thread(entered.wait, 1)
        first.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first
        second = asyncio.create_task(provider.summarize_async("second"))
        try:
            await asyncio.sleep(0.04)
            assert calls == ["first"]
            assert not second.done()
        finally:
            release.set()
        assert await asyncio.wait_for(second, 2) == "خلاصه"
        assert calls == ["first", "second"]

    asyncio.run(scenario())


def test_async_provider_reusable_across_distinct_event_loops(monkeypatch):
    provider = _provider()
    monkeypatch.setattr(provider, "summarize", lambda text, **kwargs: text)
    assert asyncio.run(provider.summarize_async("one")) == "one"
    assert asyncio.run(provider.summarize_async("two")) == "two"


def test_upload_runtime_config_and_validation():
    config = ConfigReader()
    assert configured_upload_runtime(config) == (2, 30.0)
    config.get("api.upload")["max_active_requests"] = True
    with pytest.raises(ConfigurationError, match="max_active_requests"):
        configured_upload_runtime(config)


def test_second_simultaneous_upload_gets_503_and_capacity_recovers():
    async def scenario():
        entered = asyncio.Event()
        release = asyncio.Event()
        responses: list[list[dict]] = [[], [], []]
        active_count = 0

        async def downstream(scope, receive, send):
            nonlocal active_count
            active_count += 1
            entered.set()
            try:
                if active_count == 1 and not release.is_set():
                    await release.wait()
                await JSONResponse({"ok": True})(scope, receive, send)
            finally:
                active_count -= 1

        middleware = UploadBodyLimitMiddleware(
            downstream, api_prefix="/api/v1", max_total_bytes=8,
            max_active_requests=1, admission_wait_seconds=0.03,
        )

        async def receive():
            return _body()

        async def run(index):
            async def send(message):
                responses[index].append(message)
            await middleware(_scope(), receive, send)

        first = asyncio.create_task(run(0))
        await asyncio.wait_for(entered.wait(), 1)
        await run(1)
        assert responses[1][0]["status"] == 503
        assert active_count == 1
        release.set()
        await asyncio.wait_for(first, 1)
        await run(2)
        assert responses[0][0]["status"] == 200
        assert responses[2][0]["status"] == 200

    asyncio.run(scenario())


def test_idle_upload_timeout_redacted_and_does_not_leak_capacity():
    async def scenario():
        statuses = []

        async def downstream(scope, receive, send):
            await JSONResponse({"ok": True})(scope, receive, send)

        middleware = UploadBodyLimitMiddleware(
            downstream, api_prefix="/api/v1", max_total_bytes=8,
            max_active_requests=1, idle_timeout_seconds=0.02,
        )

        async def blocked_receive():
            await asyncio.Event().wait()

        async def record_timeout(message):
            statuses.append(message)

        await middleware(_scope(), blocked_receive, record_timeout)
        assert statuses[0]["status"] == 408
        bodies = [
            message["body"] for message in statuses
            if message["type"] == "http.response.body"
        ]
        assert b"UploadReadTimeout" in b"".join(bodies)

        async def immediate_receive():
            return _body()

        next_response = []
        async def record_next(message):
            next_response.append(message)

        await middleware(_scope(), immediate_receive, record_next)
        assert next_response[0]["status"] == 200

    asyncio.run(scenario())


def test_model_busy_is_503_without_private_error_text(monkeypatch):
    async def busy(self, text, summary_length="medium"):
        raise ModelBusyError("private user text and internal details")

    monkeypatch.setattr(SummarizationService, "summarize_text_async", busy)
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/summarization/text", json={"text": "نمونه"}
        )
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "ModelBusyError"
    assert "private" not in response.text
