"""Mock-only Stage 10 v4 opt-in lead-prose fallback tests."""
from __future__ import annotations

import asyncio

import pytest

from benchmarks.quality_benchmark import BenchmarkInputError, DATASET, execute_async
from src.core.services.summarization.long_text_summarization_service import (
    LongTextSummarizationService, SummarizationInputError,
)
from src.core.services.summarization.text_chunking_service import TextChunkingService


class FakeProvider:
    max_input_tokens = 75
    max_input_characters = 90
    max_output_tokens = 120

    def __init__(self):
        self.calls = []

    def count_input_tokens(self, text):
        return len(text.strip()) + 1

    async def summarize_async(self, text, *, max_output_tokens=None):
        self.calls.append((text, max_output_tokens))
        return "خلاصه عمومی"


def build_service():
    provider = FakeProvider()
    return LongTextSummarizationService(TextChunkingService(provider), provider), provider


def run(coroutine):
    return asyncio.run(coroutine)


def test_bounded_lead_fallback_uses_only_complete_original_source_sentences():
    service, provider = build_service()
    source = (
        "# برنامه\n"
        "## 1. هدف\n"
        "چند فایل در یک درخواست پشتیبانی می‌شوند.\n"
        "خدمات عمومی و گسترده پروژه معرفی شده‌اند.\n"
        "## 2. خارج از محدوده\n"
        "OCR برای تصویر پشتیبانی می‌شود.\n"
    )
    selected = run(service._balanced_lead_final_async(source, 80))
    assert selected == "چند فایل در یک درخواست پشتیبانی می‌شوند."
    assert selected in source
    assert provider.count_input_tokens(selected) <= 80
    assert not provider.calls


def test_scope_and_code_fence_exclusions_prevent_feature_inversion():
    service, _ = build_service()
    source = (
        "## Scope\n"
        "فایل‌های `TXT` پشتیبانی می‌شوند.\n"
        "```markdown\nفایل‌های `DOC` پشتیبانی می‌شوند.\n```\n"
        "### Out of scope\n"
        "OCR برای تصاویر پشتیبانی می‌شود.\n"
        "## Later\n"
        "GPU در نسخه بعد پشتیبانی می‌شود.\n"
    )
    candidates = service._lead_source_sentences(source)
    assert candidates == ["فایل‌های `TXT` پشتیبانی می‌شوند."]
    assert "OCR" not in str(candidates) and "DOC" not in str(candidates)
    result = run(service._balanced_lead_final_async(source, 80))
    assert result == "فایل‌های `TXT` پشتیبانی می‌شوند."


def test_v4_falls_back_to_existing_map_source_when_prose_lacks_signal():
    service, provider = build_service()
    rule = "این قاعده باید رعایت شود."
    source = (
        "## 1. هدف\n"
        "توضیح عمومی بدون ادعای قابلیت مشخص.\n"
        + (f"- {rule}\n\nتوضیح تکمیلی فارسی برای طولانی شدن سند.\n\n" * 5)
    )
    old = run(service.summarize_async(
        source, "medium", preserve_map_evidence=True, source_grounded_final=True
    ))
    candidate = run(service.summarize_async(
        source, "medium", preserve_map_evidence=True,
        source_grounded_final=True, balanced_source_final=True,
    ))
    assert old == candidate
    assert rule in candidate
    assert provider.calls


def test_v4_opt_in_changes_only_final_extractive_result_when_prose_eligible():
    service, provider = build_service()
    rule = "این قاعده باید رعایت شود."
    sentence = "چند فایل در یک درخواست پشتیبانی می‌شوند."
    source = (
        "## 1. هدف\n" + sentence + "\n"
        + (f"- {rule}\n\nتوضیح تکمیلی برای طولانی شدن سند.\n\n" * 5)
    )
    before = run(service.summarize_async(
        source, "medium", preserve_map_evidence=True, source_grounded_final=True,
    ))
    after = run(service.summarize_async(
        source, "medium", preserve_map_evidence=True,
        source_grounded_final=True, balanced_source_final=True,
    ))
    assert rule in before
    assert after == sentence
    assert provider.count_input_tokens(after) <= service.output_token_budget("medium")


@pytest.mark.parametrize("flags", [
    {"balanced_source_final": True},
    {"preserve_map_evidence": True, "balanced_source_final": True},
    {"source_grounded_final": True, "balanced_source_final": True},
    {"preserve_map_evidence": True, "source_grounded_final": True, "balanced_source_final": 1},
])
def test_v4_requires_all_boolean_parent_flags(flags):
    service, provider = build_service()
    with pytest.raises(SummarizationInputError):
        run(service.summarize_async("متن کوتاه", "medium", **flags))
    assert not provider.calls


def test_v4_benchmark_refuses_holdout_and_unpaired_flags(tmp_path):
    output = tmp_path / "blocked.json"
    with pytest.raises(BenchmarkInputError, match="requires source-grounded"):
        run(execute_async(DATASET, output, ["medium"], "dev", balanced_source_final=True))
    for split in ("holdout", "all"):
        with pytest.raises(BenchmarkInputError, match="requires split=dev"):
            run(execute_async(
                DATASET, output, ["medium"], split,
                preserve_map_evidence=True,
                source_grounded_final=True,
                balanced_source_final=True,
            ))
    assert not output.exists()
