"""Lazy, process-scoped mT5 inference provider for short Persian text."""

from __future__ import annotations

import asyncio
import re
import threading
from typing import Any
from weakref import WeakKeyDictionary

from src.infrastructure.di.inject import inject
from src.infrastructure.utils.config_reader import ConfigReader, ConfigurationError


class ModelInputError(ValueError):
    """The input cannot be processed as a short text."""


class ModelLoadError(RuntimeError):
    """The model or tokenizer could not be initialized."""


class ModelInferenceError(RuntimeError):
    """Tokenization or generation failed."""


class ModelBusyError(ModelInferenceError):
    """Inference admission timed out before starting model work."""


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

        self._max_concurrent_inferences = self._require_int(
            settings, "max_concurrent_inferences", 1, 4
        )
        self._queue_wait_seconds = self._require_float(
            settings, "queue_wait_seconds", lower=0.0, inclusive=False
        )
        if self._queue_wait_seconds > 300:
            raise ConfigurationError("model.queue_wait_seconds must not exceed 300")

        self._admission_lock = threading.Lock()
        # Separate asyncio loop lifetimes must not share bound futures.
        self._async_slots: WeakKeyDictionary[
            asyncio.AbstractEventLoop, asyncio.Semaphore
        ] = WeakKeyDictionary()
        self._load_lock = threading.RLock()
        self._tokenization_lock = threading.Lock()
        self._inference_lock = threading.BoundedSemaphore(self._max_concurrent_inferences)
        self._tokenizer: Any = None
        self._model: Any = None
        self._device: str | None = None
        self._load_failure: ModelLoadError | None = None
        self._tokenizer_failure: ModelLoadError | None = None

    @property
    def max_input_tokens(self) -> int:
        return self._max_input_tokens

    @property
    def max_input_characters(self) -> int:
        return self._max_input_characters

    @property
    def max_output_tokens(self) -> int:
        return self._max_output_tokens

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

    def _ensure_tokenizer_loaded(self) -> None:
        """Initialize the pinned tokenizer once, without loading model weights."""
        if self._tokenizer is not None:
            return
        with self._load_lock:
            if self._tokenizer is not None:
                return
            if self._tokenizer_failure is not None:
                raise self._tokenizer_failure
            try:
                from transformers import AutoTokenizer

                self._tokenizer = AutoTokenizer.from_pretrained(
                    self._model_id,
                    revision=self._revision,
                    use_fast=False,
                    trust_remote_code=False,
                )
            except Exception as error:
                failure = ModelLoadError(
                    "Failed to initialize the configured mT5 tokenizer; "
                    "check dependencies, Hugging Face access and cache"
                )
                self._tokenizer_failure = failure
                raise failure from error

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
                from transformers import AutoModelForSeq2SeqLM

                device = self._device_setting
                if device == "auto":
                    device = "cuda" if torch.cuda.is_available() else "cpu"
                if device == "cuda" and not torch.cuda.is_available():
                    raise RuntimeError("CUDA was selected but is unavailable")

                self._ensure_tokenizer_loaded()
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
            self._model = model
            self._device = device

    def count_input_tokens(self, text: str) -> int:
        """Count model input tokens including specials without loading weights.

        The same edge-trimming and special-token policy is used for inference.
        Input to this method is bounded by the provider's character budget.
        """
        if not isinstance(text, str) or not text.strip():
            raise ModelInputError("text must be a non-empty string")
        text = text.strip()
        if len(text) > self._max_input_characters:
            raise ModelInputError(
                f"text exceeds {self._max_input_characters} characters; use chunking"
            )
        self._ensure_tokenizer_loaded()
        try:
            with self._tokenization_lock:
                encoded = self._tokenizer(
                    text,
                    add_special_tokens=True,
                    padding=False,
                    truncation=False,
                    return_attention_mask=False,
                    return_tensors=None,
                )
            return len(encoded["input_ids"])
        except Exception as error:
            raise ModelInferenceError("mT5 input token counting failed") from error

    def summarize(self, text: str, *, max_output_tokens: int | None = None) -> str:
        """Synchronously summarize one short text (blocks the calling thread)."""
        if not isinstance(text, str) or not text.strip():
            raise ModelInputError("text must be a non-empty string")
        text = text.strip()
        if len(text) > self._max_input_characters:
            raise ModelInputError(
                f"text exceeds {self._max_input_characters} characters; use chunking"
            )
        output_limit = self._max_output_tokens if max_output_tokens is None else max_output_tokens
        if type(output_limit) is not int or not 1 <= output_limit <= self._max_output_tokens:
            raise ModelInputError(
                f"max_output_tokens must be in [1, {self._max_output_tokens}]"
            )
        self._ensure_loaded()
        with self._inference_lock:
            try:
                import torch

                with self._tokenization_lock:
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
                        max_length=output_limit,
                        num_beams=self._num_beams,
                        repetition_penalty=self._repetition_penalty,
                        length_penalty=self._length_penalty,
                        early_stopping=self._early_stopping,
                        do_sample=False,
                    )
                with self._tokenization_lock:
                    summary = self._tokenizer.decode(
                        generated[0],
                        skip_special_tokens=True,
                        clean_up_tokenization_spaces=True,
                    )
                if not isinstance(summary, str) or not summary.strip():
                    raise ModelOutputError("mT5 returned an empty summary")
                return summary.strip()
            except (ModelInputError, ModelOutputError):
                raise
            except Exception as error:
                raise ModelInferenceError("mT5 tokenization or generation failed") from error

    def _slots_for_running_loop(self) -> asyncio.Semaphore:
        loop = asyncio.get_running_loop()
        with self._admission_lock:
            slots = self._async_slots.get(loop)
            if slots is None:
                slots = asyncio.Semaphore(self._max_concurrent_inferences)
                self._async_slots[loop] = slots
            return slots

    async def summarize_async(
        self, text: str, *, max_output_tokens: int | None = None
    ) -> str:
        """Bound admission and retain capacity until work really finishes.

        Queue wait timeout is not a generation timeout. Request cancellation
        cannot forcibly stop a Python worker thread once inference has started.
        """
        slots = self._slots_for_running_loop()
        try:
            await asyncio.wait_for(
                slots.acquire(), timeout=self._queue_wait_seconds
            )
        except TimeoutError as error:
            raise ModelBusyError(
                "mT5 inference capacity is temporarily unavailable"
            ) from error

        try:
            task = asyncio.create_task(
                asyncio.to_thread(
                    self.summarize, text, max_output_tokens=max_output_tokens
                )
            )
        except BaseException:
            slots.release()
            raise

        def finish(done: asyncio.Task[str]) -> None:
            slots.release()
            # A disconnected client no longer awaits the result.
            if not done.cancelled():
                done.exception()

        task.add_done_callback(finish)
        return await asyncio.shield(task)
