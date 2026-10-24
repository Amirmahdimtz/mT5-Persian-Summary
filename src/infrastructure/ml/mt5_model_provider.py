"""Lazy, process-scoped mT5 inference provider for short Persian text."""

from __future__ import annotations

import asyncio
import re
import threading
from typing import Any

from src.infrastructure.di.inject import inject
from src.infrastructure.utils.config_reader import ConfigReader, ConfigurationError


class ModelInputError(ValueError):
    """The input cannot be processed as a short text."""


class ModelLoadError(RuntimeError):
    """The model or tokenizer could not be initialized."""


class ModelInferenceError(RuntimeError):
    """Tokenization or generation failed."""


class ModelOutputError(ModelInferenceError):
    """The model returned no usable summary."""


@inject
class Mt5ModelProvider:
    """Load weights lazily once per DI instance and serialize inference per worker.

    Resolve through DI to obtain the process-local singleton. The synchronous
    method is intended for CLI and worker threads; use summarize_async in ASGI.
    """

    __di_singleton__ = True

    def __init__(self, config_reader: ConfigReader) -> None:
        settings = config_reader.get("model")
        if not isinstance(settings, dict):
            raise ConfigurationError("model must be a configuration mapping")

        self._model_id = self._require_str(settings, "id")
        self._revision = self._require_str(settings, "revision")
        if not re.fullmatch(r"[0-9a-f]{40}", self._revision):
            raise ConfigurationError("model.revision must be a full 40-character SHA")
        self._device_setting = self._require_str(settings, "device")
        if self._device_setting not in ("cpu", "cuda", "auto"):
            raise ConfigurationError("model.device must be cpu, cuda or auto")

        self._max_input_tokens = self._require_int(settings, "max_input_tokens", 1, 1000)
        self._max_input_characters = self._require_int(
            settings, "max_input_characters", 1, 20000
        )
        self._max_output_tokens = self._require_int(settings, "max_output_tokens", 1, 512)
        self._num_beams = self._require_int(settings, "num_beams", 1, 8)
        self._repetition_penalty = self._require_float(
            settings, "repetition_penalty", lower=0.0, inclusive=False
        )
        self._length_penalty = self._require_float(
            settings, "length_penalty", lower=0.0, inclusive=False
        )
        self._early_stopping = settings.get("early_stopping")
        if type(self._early_stopping) is not bool:
            raise ConfigurationError("model.early_stopping must be a boolean")

        self._load_lock = threading.Lock()
        self._inference_lock = threading.Lock()
        self._tokenizer: Any = None
        self._model: Any = None
        self._device: str | None = None
        self._load_failure: ModelLoadError | None = None

    @staticmethod
    def _require_str(settings: dict[str, Any], key: str) -> str:
        value = settings.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ConfigurationError(f"model.{key} must be a non-empty string")
        return value.strip()

    @staticmethod
    def _require_int(settings: dict[str, Any], key: str, low: int, high: int) -> int:
        value = settings.get(key)
        if type(value) is not int or not low <= value <= high:
            raise ConfigurationError(f"model.{key} must be an integer in [{low}, {high}]")
        return value

    @staticmethod
    def _require_float(
        settings: dict[str, Any], key: str, *, lower: float, inclusive: bool
    ) -> float:
        value = settings.get(key)
        if type(value) not in (int, float):
            raise ConfigurationError(f"model.{key} must be numeric")
        number = float(value)
        import math

        if not math.isfinite(number) or (number < lower if inclusive else number <= lower):
            raise ConfigurationError(f"model.{key} must be finite and positive")
        return number

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        with self._load_lock:
            if self._model is not None:
                return
            if self._load_failure is not None:
                raise self._load_failure
            try:
                import torch
                from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

                device = self._device_setting
                if device == "auto":
                    device = "cuda" if torch.cuda.is_available() else "cpu"
                if device == "cuda" and not torch.cuda.is_available():
                    raise RuntimeError("CUDA was selected but is unavailable")

                tokenizer = AutoTokenizer.from_pretrained(
                    self._model_id,
                    revision=self._revision,
                    use_fast=False,
                    trust_remote_code=False,
                )
                model = AutoModelForSeq2SeqLM.from_pretrained(
                    self._model_id,
                    revision=self._revision,
                    trust_remote_code=False,
                    use_safetensors=False,  # This exact checkpoint ships only pytorch_model.bin.
                    weights_only=True,
                )
                model.to(device)
                model.eval()
            except Exception as error:
                failure = ModelLoadError(
                    "Failed to initialize the configured mT5 checkpoint; "
                    "check dependencies, Hugging Face access, cache, device and RAM"
                )
                self._load_failure = failure
                raise failure from error
            self._tokenizer = tokenizer
            self._model = model
            self._device = device

    def summarize(self, text: str) -> str:
        """Synchronously summarize one short text (blocks the calling thread)."""
        if not isinstance(text, str) or not text.strip():
            raise ModelInputError("text must be a non-empty string")
        text = text.strip()
        if len(text) > self._max_input_characters:
            raise ModelInputError(
                f"text exceeds {self._max_input_characters} characters; use chunking"
            )
        self._ensure_loaded()
        with self._inference_lock:
            try:
                import torch

                encoded = self._tokenizer(
                    text,
                    add_special_tokens=True,
                    padding=False,
                    truncation=False,
                    return_attention_mask=True,
                    return_tensors="pt",
                )
                token_count = encoded["input_ids"].shape[-1]
                if token_count > self._max_input_tokens:
                    raise ModelInputError(
                        f"text requires {token_count} tokens; maximum is "
                        f"{self._max_input_tokens}; use chunking"
                    )
                inputs = {key: encoded[key].to(self._device) for key in ("input_ids", "attention_mask")}
                with torch.inference_mode():
                    generated = self._model.generate(
                        **inputs,
                        max_length=self._max_output_tokens,
                        num_beams=self._num_beams,
                        repetition_penalty=self._repetition_penalty,
                        length_penalty=self._length_penalty,
                        early_stopping=self._early_stopping,
                        do_sample=False,
                    )
                summary = self._tokenizer.decode(
                    generated[0], skip_special_tokens=True, clean_up_tokenization_spaces=True
                )
                if not isinstance(summary, str) or not summary.strip():
                    raise ModelOutputError("mT5 returned an empty summary")
                return summary.strip()
            except (ModelInputError, ModelOutputError):
                raise
            except Exception as error:
                raise ModelInferenceError("mT5 tokenization or generation failed") from error

    async def summarize_async(self, text: str) -> str:
        """Run CPU/GPU-bound inference in a thread without blocking the event loop."""
        return await asyncio.to_thread(self.summarize, text)
