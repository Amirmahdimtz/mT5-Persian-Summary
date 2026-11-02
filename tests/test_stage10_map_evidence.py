"""Mock-only Stage 10 source-grounded Map ablation tests; no weights or network."""

from __future__ import annotations

import asyncio

import pytest

from benchmarks.quality_benchmark import BenchmarkInputError, DATASET, execute_async
from src.core.services.summarization.long_text_summarization_service import (
    LongTextSummarizationService,
    SummarizationInputError,
)
from src.core.services.summarization.text_chunking_service import TextChunkingService


class FakeProvider:
    max_input_tokens = 90
    max_input_characters = 100
    max_output_tokens = 42

    def __init__(self):
        self.calls = []

    def count_input_tokens(self, text):
        return len(text.strip()) + 1

    async def summarize_async(self, text, *, max_output_tokens=None):
        self.calls.append((text, max_output_tokens))
        return "خلاصه"


def build_service(provider=None):
    provider = provider or FakeProvider()
    return LongTextSummarizationService(TextChunkingService(provider), provider), provider


def test_generic_source_bullets_are_selected_without_fixture_fact_ids():
    selection = LongTextSummarizationService._evidence_lines(
        "زمینه\n- این بخش باید در گزارش باشد. توضیح اضافه.\n"
        "- عدد ۱۲۳ در سند ثبت شد.\n"
        "```\n- دستور کد نباید به خلاصه افزوده شود.\n```\n"
        "- سطر کاملاً معمولی بدون علامت\n"
    )
    assert "این بخش باید در گزارش باشد." in selection
    assert "عدد ۱۲۳ در سند ثبت شد." in selection
    assert all("دستور کد" not in item for item in selection)
    assert all("توضیح اضافه" not in item for item in selection)
    assert len(selection) <= 3


def test_only_source_quotes_are_added_to_intermediate_map_outputs():
    service, provider = build_service()
    source = ("- این قاعده باید رعایت شود.\n\nبخش دیگری از سند ارائه شده است.\n\n" * 3)
    result = asyncio.run(service.summarize_async(source, "medium", preserve_map_evidence=True))
    assert result == "خلاصه"
    assert len(provider.calls) >= 3
    # An intermediate model input contains a literal source sentence alongside
    # generated content, proving the Map ablation is actually wired in.
    assert any(
        "خلاصه\nاین قاعده باید رعایت شود." in value
        for value, _ in provider.calls
    )
    assert all(limit <= provider.max_output_tokens for _, limit in provider.calls)


def test_default_hierarchical_path_is_not_modified():
    source = ("- این قاعده باید رعایت شود.\n\nمتن دیگری آمده است.\n\n" * 3)
    service, provider = build_service()
    asyncio.run(service.summarize_async(source, "medium"))
    assert all(
        "خلاصه\nاین قاعده باید رعایت شود." not in value
        for value, _ in provider.calls
    )


def test_trial_fails_safe_when_evidence_cannot_fit_budget():
    provider = FakeProvider()
    provider.max_output_tokens = 9
    service, _ = build_service(provider)
    summary = asyncio.run(
        service._augment_map_async(
            "- جمله اول باید در سند باقی بماند.", "خلاصه"
        )
    )
    assert summary == "خلاصه"
    assert provider.count_input_tokens(summary) <= provider.max_output_tokens


def test_reject_non_boolean_trial_flag():
    service, provider = build_service()
    with pytest.raises(SummarizationInputError, match="boolean"):
        asyncio.run(service.summarize_async("متن", "medium", preserve_map_evidence=1))
    assert provider.calls == []


def test_map_trial_refuses_all_and_holdout_before_bootstrapping(tmp_path):
    for split in ("all", "holdout"):
        with pytest.raises(BenchmarkInputError, match="requires split=dev"):
            asyncio.run(execute_async(
                DATASET, tmp_path / "not-created.json", ["medium"], split,
                preserve_map_evidence=True,
            ))
    assert not (tmp_path / "not-created.json").exists()


def test_default_benchmark_input_type_is_checked(tmp_path):
    with pytest.raises(BenchmarkInputError, match="boolean"):
        asyncio.run(execute_async(
            DATASET, tmp_path / "not-created.json", ["medium"], "dev",
            preserve_map_evidence="yes",
        ))
