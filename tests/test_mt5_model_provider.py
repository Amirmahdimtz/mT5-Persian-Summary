"""Mock-only mT5 provider tests; never download the model in pytest."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
import sys
from types import ModuleType
from unittest.mock import Mock

import pytest

from src.infrastructure.di.bootstrap import bootstrap_di
from src.infrastructure.di.inject import resolve
from src.infrastructure.ml.mt5_model_provider import (
    ModelInferenceError,
    ModelInputError,
    ModelLoadError,
    ModelOutputError,
    Mt5ModelProvider,
)
from src.infrastructure.utils.config_reader import ConfigReader, ConfigurationError


class FakeTensor:
    def __init__(self, length: int) -> None:
        self.shape = (1, length)
        self.device = "cpu"

    def to(self, device: str) -> FakeTensor:
        self.device = device
        return self


@pytest.fixture
def mocked_backend(monkeypatch: pytest.MonkeyPatch):
    tokenizer = Mock()
    tokenizer.return_value = {
        "input_ids": FakeTensor(18),
        "attention_mask": FakeTensor(18),
    }
    tokenizer.decode.return_value = "  خلاصهٔ فارسی  "
    model = Mock()
    model.generate.return_value = [[14, 25]]
    tokenizer_factory = Mock()
    tokenizer_factory.from_pretrained.return_value = tokenizer
    model_factory = Mock()
    model_factory.from_pretrained.return_value = model
    transformers = ModuleType("transformers")
    transformers.AutoTokenizer = tokenizer_factory
    transformers.AutoModelForSeq2SeqLM = model_factory
    torch = ModuleType("torch")
    torch.cuda = Mock()
    torch.cuda.is_available.return_value = False
    torch.inference_mode = nullcontext
    monkeypatch.setitem(sys.modules, "transformers", transformers)
    monkeypatch.setitem(sys.modules, "torch", torch)
    return tokenizer, model, tokenizer_factory, model_factory, torch


def provider_with_config(**overrides) -> Mt5ModelProvider:
    config = ConfigReader()
    config.get("model").update(overrides)
    return Mt5ModelProvider(config)


def test_discovery_and_process_singleton_do_not_load_model():
    bootstrap_di()
    a = resolve(Mt5ModelProvider)
    assert a is resolve(Mt5ModelProvider)
    assert a._model is None
    assert a._tokenizer is None
    assert a._model_id == "nafisehNik/mt5-persian-summary"


def test_config_selected_in_both_environments(monkeypatch: pytest.MonkeyPatch):
    for env in ("development", "production"):
        monkeypatch.setenv("env_type", env)
        config = ConfigReader()
        assert config.get("model.revision") == "b575560ad967050e77a40f907abb1ebbeefb9a15"
        assert provider_with_config()._max_input_tokens == 1000


@pytest.mark.parametrize("invalid", [None, 1, {}, "", "  ", ["hello"]])
def test_invalid_text_rejected_without_loading(invalid):
    provider = provider_with_config()
    with pytest.raises(ModelInputError):
        provider.summarize(invalid)
    assert provider._model is None


def test_oversized_char_input_rejected_without_loading():
    provider = provider_with_config()
    with pytest.raises(ModelInputError, match="characters"):
        provider.summarize("آ" * 20001)
    assert provider._model is None


def test_token_count_oversized_without_silent_truncation(mocked_backend):
    tokenizer, _, _, _, _ = mocked_backend
    tokenizer.return_value["input_ids"] = FakeTensor(1001)
    provider = provider_with_config()
    with pytest.raises(ModelInputError, match="1001 tokens"):
        provider.summarize("متن")
    assert tokenizer.call_args.kwargs["truncation"] is False
    assert tokenizer.call_args.kwargs["padding"] is False


def test_valid_generation_and_decode(mocked_backend):
    tokenizer, model, tok_factory, model_factory, _ = mocked_backend
    provider = provider_with_config()
    assert provider.summarize("  متن کوتاه  ") == "خلاصهٔ فارسی"
    assert tok_factory.from_pretrained.call_args.kwargs["use_fast"] is False
    assert model_factory.from_pretrained.call_args.kwargs["weights_only"] is True
    assert model_factory.from_pretrained.call_args.kwargs["trust_remote_code"] is False
    assert model_factory.from_pretrained.call_args.kwargs["revision"] == provider._revision
    assert model.eval.call_count == 1
    assert model.to.call_args.args == ("cpu",)
    assert tokenizer.call_args.args == ("متن کوتاه",)
    assert model.generate.call_args.kwargs["max_length"] == 120
    assert model.generate.call_args.kwargs["num_beams"] == 2
    assert model.generate.call_args.kwargs["do_sample"] is False
    assert model.generate.call_args.kwargs["input_ids"].device == "cpu"


def test_repeated_summaries_reuse_model_and_tokenizer(mocked_backend):
    _, _, tokenizer_factory, model_factory, _ = mocked_backend
    provider = provider_with_config()
    provider.summarize("متن اول")
    provider.summarize("متن دوم")
    assert model_factory.from_pretrained.call_count == 1
    assert tokenizer_factory.from_pretrained.call_count == 1


def test_empty_decoded_summary_is_reported(mocked_backend):
    tokenizer = mocked_backend[0]
    tokenizer.decode.return_value = "  "
    with pytest.raises(ModelOutputError, match="empty summary"):
        provider_with_config().summarize("متن")


def test_loading_failure_is_cached(mocked_backend):
    tokenizer_factory = mocked_backend[2]
    tokenizer_factory.from_pretrained.side_effect = OSError("private token")
    provider = provider_with_config()
    for _ in range(2):
        with pytest.raises(ModelLoadError, match="Failed to initialize") as exc:
            provider.summarize("متن")
        assert "private token" not in str(exc.value)
    assert tokenizer_factory.from_pretrained.call_count == 1


def test_generation_failure_is_wrapped_without_text_leak(mocked_backend):
    model = mocked_backend[1]
    model.generate.side_effect = RuntimeError("private text")
    with pytest.raises(ModelInferenceError, match="mT5 tokenization") as exc:
        provider_with_config().summarize("محرمانه")
    assert "محرمانه" not in str(exc.value)
    assert "private text" not in str(exc.value)


def test_invalid_config_is_rejected_before_model_loading():
    for change in (
        {"device": "tpu"},
        {"revision": "main"},
        {"max_input_tokens": 0},
        {"max_output_tokens": True},
        {"num_beams": 0},
        {"length_penalty": float("nan")},
        {"repetition_penalty": 0},
        {"early_stopping": "yes"},
    ):
        with pytest.raises(ConfigurationError):
            provider_with_config(**change)


def test_explicit_unavailable_cuda_rejected(mocked_backend):
    with pytest.raises(ModelLoadError, match="Failed to initialize"):
        provider_with_config(device="cuda").summarize("متن")


def test_load_once_across_simultaneous_calls(mocked_backend):
    _, _, tokenizer_factory, model_factory, _ = mocked_backend
    provider = provider_with_config()
    with ThreadPoolExecutor(max_workers=8) as executor:
        outputs = list(executor.map(provider.summarize, ["متن"] * 16))
    assert outputs == ["خلاصهٔ فارسی"] * 16
    assert tokenizer_factory.from_pretrained.call_count == 1
    assert model_factory.from_pretrained.call_count == 1


def test_async_inference_uses_thread_without_blocking_loop(mocked_backend):
    provider = provider_with_config()
    assert asyncio.run(provider.summarize_async("متن")) == "خلاصهٔ فارسی"


def test_cpu_auto_selection(mocked_backend):
    provider = provider_with_config(device="auto")
    assert provider.summarize("متن") == "خلاصهٔ فارسی"
    assert provider._device == "cpu"
