"""Offline tests for Stage 10's opt-in source-only final Reduce fallback.

The test provider is deterministic and does not load mT5 weights.
"""
from __future__ import annotations

import asyncio

import pytest

from benchmarks.quality_benchmark import BenchmarkInputError, DATASET, execute_async
from src.core.services.summarization.long_text_summarization_service import (
    LongTextSummarizationService, SummarizationInputError,
)
from src.core.services.summarization.text_chunking_service import TextChunkingService


class FakeModel:
    max_input_tokens = 75
    max_input_characters = 90
    max_output_tokens = 120

    def __init__(self):
        self.calls: list[tuple[str, int | None]] = []

    def count_input_tokens(self, text: str) -> int:
        return len(text.strip()) + 1

    async def summarize_async(self, text: str, *, max_output_tokens: int | None = None) -> str:
        self.calls.append((text, max_output_tokens))
        return "خلاصه عمومی"


def service(model=None):
    model = model or FakeModel()
    return LongTextSummarizationService(TextChunkingService(model), model), model


def run(coro):
    return asyncio.run(coro)


def test_extractive_final_is_verbatim_and_within_final_token_budget():
    svc, model = service()
    rule = "این تصمیم باید رعایت شود."
    source = (f"- {rule}\n\nتوضیح کوتاه و متن تکمیلی.\n\n" * 5).strip()
    original_result = run(svc.summarize_async(
        source, "medium", preserve_map_evidence=True,
    ))
    assert original_result == "خلاصه عمومی"
    actual = run(svc.summarize_async(
        source, "medium", preserve_map_evidence=True,
        source_grounded_final=True,
    ))
    assert rule in actual
    assert "خلاصه عمومی" not in actual
    assert all(line in source for line in actual.splitlines())
    assert model.count_input_tokens(actual) <= svc.output_token_budget("medium")
    assert model.calls


def test_no_source_bullets_falls_back_to_generated_model_summary():
    svc, _ = service()
    source = ("این فقط یک متن عادی است. " * 9).strip()
    result = run(svc.summarize_async(
        source, "medium", preserve_map_evidence=True,
        source_grounded_final=True,
    ))
    assert result == "خلاصه عمومی"


def test_fallback_never_truncates_source_excerpt_to_fit_budget():
    svc, model = service()
    model.max_output_tokens = 12
    source = "- جمله بسیار طولانی باید بدون قطع شدن حفظ شود."
    output = run(svc._final_source_evidence_async([source], final_budget=8))
    assert output is None


def test_direct_input_keeps_original_model_result():
    svc, model = service()
    result = run(svc.summarize_async(
        "متن کوتاه", "medium", preserve_map_evidence=True,
        source_grounded_final=True,
    ))
    assert result == "خلاصه عمومی"
    assert len(model.calls) == 1


@pytest.mark.parametrize("kwargs", [
    {"source_grounded_final": True},
    {"preserve_map_evidence": "yes", "source_grounded_final": True},
    {"preserve_map_evidence": True, "source_grounded_final": 1},
])
def test_invalid_or_unpaired_experiment_flags_are_rejected(kwargs):
    svc, model = service()
    with pytest.raises(SummarizationInputError):
        run(svc.summarize_async("متن فارسی", "medium", **kwargs))
    assert not model.calls


def test_dev_only_cli_trial_rejects_holdout_and_unpaired_options(tmp_path):
    output = tmp_path / "never.json"
    with pytest.raises(BenchmarkInputError, match="requires map evidence"):
        run(execute_async(
            DATASET, output, ["medium"], "dev", source_grounded_final=True,
        ))
    for split in ("all", "holdout"):
        with pytest.raises(BenchmarkInputError, match="requires split=dev"):
            run(execute_async(
                DATASET, output, ["medium"], split,
                preserve_map_evidence=True, source_grounded_final=True,
            ))
    assert not output.exists()


def test_excluded_markdown_scope_is_not_extracted_as_a_positive_claim():
    source = (
        "## داخل محدوده\n"
        "- خلاصه‌سازی فایل باید فعال شود.\n"
        "### موارد مجاز\n"
        "- بررسی عدد ۱۲۳ در درخواست ضروری است.\n"
        "## خارج از محدوده نسخه اول\n"
        "- پشتیبانی از `.doc`، فایل‌های Office دیگر یا تصویر.\n"
        "### جزئیات خارج از محدوده\n"
        "- نباید تصویر اسکن‌شده را جزو امکانات دانست.\n"
        "## امکانات بعدی\n"
        "- استفاده از @inject باید رعایت شود.\n"
    )
    lines = LongTextSummarizationService._evidence_lines(source)
    assert "خلاصه‌سازی فایل باید فعال شود." in lines
    assert "استفاده از @inject باید رعایت شود." in lines
    assert all("Office" not in x and "اسکن‌شده" not in x for x in lines)
    excluded = LongTextSummarizationService._excluded_original_clauses(source)
    assert "پشتیبانی از `.doc`، فایل‌های Office دیگر یا تصویر." in excluded
    assert "نباید تصویر اسکن‌شده را جزو امکانات دانست." in excluded
    assert "استفاده از @inject باید رعایت شود." not in excluded


def test_full_document_exclusion_context_survives_chunk_boundaries():
    svc, _ = service()
    invalid = "پشتیبانی از `.doc`، فایل‌های Office دیگر یا تصویر."
    allowed = "این تصمیم باید رعایت شود."
    source = (
        f"## داخل محدوده\n- {allowed}\n\n"
        + "متن تکمیلی فارسی برای جداسازی بخش‌ها. " * 3
        + f"\n\n## خارج از محدوده نسخه اول\n- {invalid}\n\n"
        + "متن غیرحساس برای عبور از مرز چانک. " * 3
    )
    # Source-level context is tracked independently of where token-aware
    # chunk boundaries fall; a prohibition cannot become a positive claim.
    assert invalid in svc._excluded_original_clauses(source)
    result = run(svc.summarize_async(
        source, "medium", preserve_map_evidence=True,
        source_grounded_final=True,
    ))
    assert allowed in result
    assert invalid not in result
    assert "Office" not in result


def test_english_out_of_scope_section_is_excluded_as_well():
    text = (
        "## Supported\n- API باید فعال شود.\n"
        "## Out of scope\n- PDF scanning باید فعال شود.\n"
    )
    assert LongTextSummarizationService._evidence_lines(text) == [
        "API باید فعال شود."
    ]


def test_future_backlog_heading_does_not_present_planned_feature_as_live():
    source = (
        "## قابلیت‌های کنونی\n"
        "- این قابلیت باید در سرویس فعال باشد.\n"
        "## 9. فاز دوم (صرفاً Backlog، نه بخشی از هشت مرحله)\n"
        "- OCR برای PDFهای اسکن‌شده.\n"
        "- Storage و پایگاه داده در آینده طراحی می‌شوند.\n"
        "### قابلیت‌های پیشنهادی\n"
        "- GPU Inference و پردازش Batch.\n"
        "## تعهدهای نسخه اول\n"
        "- ثبت خطا ضروری است.\n"
    )
    selected = LongTextSummarizationService._evidence_lines(source)
    assert "این قابلیت باید در سرویس فعال باشد." in selected
    assert "ثبت خطا ضروری است." in selected
    assert all("OCR" not in line and "Storage" not in line and "GPU" not in line
               for line in selected)
    excluded = LongTextSummarizationService._excluded_original_clauses(source)
    assert "OCR برای PDFهای اسکن‌شده." in excluded
    assert "GPU Inference و پردازش Batch." in excluded
    assert "ثبت خطا ضروری است." not in excluded


def test_original_mvp_plan_backlog_clause_remains_excluded_across_chunks():
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "IMPLEMENTATION_PLAN.md").read_text(
        encoding="utf-8"
    )
    assert "فاز دوم (صرفاً Backlog" in source
    forbidden = "OCR برای PDFهای اسکن‌شده."
    assert forbidden in LongTextSummarizationService._excluded_original_clauses(source)
    # A chunk which lacks the preceding heading could still select the
    # sentence; full-source exclusion must prevent final scope inversion.
    assert forbidden in LongTextSummarizationService._evidence_lines("- " + forbidden)
