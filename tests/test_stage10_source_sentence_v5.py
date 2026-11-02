"""Stage 10 v5 extractive trial: fake tokenizer/model, no network or weights."""
from __future__ import annotations

import asyncio

import pytest

from benchmarks.quality_benchmark import BenchmarkInputError, DATASET, execute_async
from src.core.services.summarization.long_text_summarization_service import (
    LongTextSummarizationService, SummarizationInputError, SummarizationNoProgressError,
)
from src.core.services.summarization.text_chunking_service import (
    ChunkingLimitError, TextChunkingService,
)


class FakeProvider:
    max_input_tokens = 25
    max_input_characters = 2000
    max_output_tokens = 48

    def __init__(self):
        self.calls = []

    def count_input_tokens(self, text: str) -> int:
        return len(text.split()) + 1

    async def summarize_async(self, value: str, *, max_output_tokens=None) -> str:
        self.calls.append((value, max_output_tokens))
        return "generated model claim"


def service(provider=None):
    provider = provider or FakeProvider()
    return LongTextSummarizationService(TextChunkingService(provider), provider), provider


def run(coro):
    return asyncio.run(coro)


FLAGS = {
    "preserve_map_evidence": True,
    "source_grounded_final": True,
    "balanced_source_final": True,
    "source_sentence_final": True,
}


def test_v5_preserves_full_source_direction_and_numbers_without_model_inference():
    svc, provider = service()
    text = (
        "هزینه نگهداری شبکه از ۸۰ به ۶۵ میلیون تومان کاهش یافته است. "
        "در مقابل هزینه پشتیبانی نرم‌افزار از ۳۰ به ۳۶ میلیون تومان افزایش یافته است. "
        "قرارداد پشتیبانی در پایان آذر بازنگری می‌شود."
    )
    result = run(svc.summarize_async(text, "medium", **FLAGS))
    assert "کاهش یافته است." in result
    assert "افزایش یافته است." in result
    assert "از ۳۰ به ۳۶" in result
    assert all(line in text for line in result.splitlines())
    assert provider.count_input_tokens(result) <= svc.output_token_budget("medium")
    assert provider.calls == []


def test_v5_short_medium_long_are_bounded_and_give_distinct_evidence():
    svc, provider = service()
    text = (
        "برنامه جدید توسعه خدمات در شهر آغاز شد. "
        "تعداد اتوبوس‌های برقی در شهر افزایش پیدا کرد. "
        "هدف برنامه کاهش آلودگی هوا اعلام شد. "
        "دو درمانگاه جدید برای شهروندان افتتاح شد. "
        "مراکز جدید در محله‌های کم‌برخوردار فعال شدند. "
        "دانشگاه‌ها تفاهم‌نامه همکاری پژوهشی امضا کردند."
    )
    results = {tier: run(svc.summarize_async(text, tier, **FLAGS))
               for tier in ("short", "medium", "long")}
    assert len({results["short"], results["long"]}) == 2
    assert len(results["short"].splitlines()) == 1
    assert len(results["medium"].splitlines()) >= 2
    assert len(results["long"].splitlines()) >= len(results["medium"].splitlines())
    for tier, output in results.items():
        assert provider.count_input_tokens(output) <= svc.output_token_budget(tier)
        assert all(line in text for line in output.splitlines())
    assert provider.calls == []


def test_v5_long_repeated_prose_deduplicates_without_inventing_facts():
    svc, provider = service()
    paragraph = (
        "وزارت آموزش برنامه جدیدی معرفی کرد. "
        "این برنامه شامل آموزش معلمان و ارتقای زیرساخت مدارس است. "
        "اجرای برنامه مرحله‌ای است و مناطق کم‌برخوردار اولویت دارند. "
    )
    text = paragraph * 20
    assert not svc._chunker.fits(text)
    output = run(svc.summarize_async(text, "long", **FLAGS))
    assert output.count("آموزش معلمان") <= 1
    assert "مناطق کم‌برخوردار اولویت دارند" in output
    assert all(line in text for line in output.splitlines())
    assert provider.calls == []


def test_v5_preserves_markdown_scope_and_does_not_extract_fenced_code():
    svc, provider = service()
    text = (
        "## قابلیت‌های فعلی\n"
        "- متن فارسی در برنامه پردازش می‌شود.\n"
        "### موارد مجاز\n"
        "- فایل‌های متنی نیز پشتیبانی می‌شوند.\n"
        "## خارج از محدوده\n"
        "- OCR برای تصاویر پشتیبانی می‌شود.\n"
        "### توضیح بیشتر\n"
        "در آینده سرویس دیگر پشتیبانی می‌شود.\n"
        "## بخش‌های دیگر\n"
        "```\nاین قابلیت محرمانه اجرا می‌شود.\n```\n"
    )
    sentences = svc._source_sentence_candidates(text)
    joined = "\n".join(sentence for _, sentence in sentences)
    assert "متن فارسی" in joined
    assert "فایل‌های متنی" in joined
    assert "OCR" not in joined
    assert "در آینده" not in joined
    assert "محرمانه" not in joined


def test_v5_fails_closed_when_no_source_sentence_fits():
    svc, provider = service()
    text = "یک عبارت بدون نشانه پایان و بدون نقطه"
    with pytest.raises(SummarizationNoProgressError, match="no complete source sentence"):
        run(svc.summarize_async(text, "medium", **FLAGS))
    assert provider.calls == []


@pytest.mark.parametrize("options", [
    {"source_sentence_final": True},
    {"balanced_source_final": True, "source_sentence_final": True},
    {"preserve_map_evidence": True, "source_grounded_final": True, "source_sentence_final": True},
    {"preserve_map_evidence": True, "source_grounded_final": True,
     "balanced_source_final": True, "source_sentence_final": 1},
])
def test_v5_invalid_optin_flags_fail_before_inference(options):
    svc, provider = service()
    with pytest.raises(SummarizationInputError):
        run(svc.summarize_async("متن آزمایشی", "medium", **options))
    assert provider.calls == []


def test_v5_benchmark_only_allows_dev_and_requires_parent_flags(tmp_path):
    output = tmp_path / "invalid.json"
    with pytest.raises(BenchmarkInputError, match="requires balanced-source"):
        run(execute_async(DATASET, output, ["medium"], "dev", source_sentence_final=True))
    for split in ("holdout", "all"):
        with pytest.raises(BenchmarkInputError, match="requires split=dev"):
            run(execute_async(
                DATASET, output, ["medium"], split, source_sentence_final=True,
                preserve_map_evidence=True, source_grounded_final=True,
                balanced_source_final=True,
            ))
    assert not output.exists()


def test_v5_default_behavior_and_existing_v4_flags_unchanged():
    svc, provider = service()
    output = run(svc.summarize_async("این متن فارسی کوتاه است.", "medium"))
    assert output == "generated model claim"
    assert provider.calls


def test_v5_rejoins_pdf_display_wrapped_sentence_across_single_blank_spacer():
    svc, provider = service()
    # pypdf layout can emit a blank line between physical lines of one sentence.
    text = (
        "گزارش نمونه فارسی برای آزمایش پردازش اسناد\n\n\n"
        "هدف از پردازش خودکار متن آن است که نکات مهم با کمترین خطا استخراج\n\n"
        "شود و خواننده بتواند تصویری روشن از موضوع به دست آورد.\n\n\n"
        "۱ . مقدمه\n\n"
        "در بخش دوم زمان رسیدگی به خرابی‌ها کاهش یافته است."
    )
    sentences = [sentence for _, sentence in svc._source_sentence_candidates(text)]
    assert sentences == [
        "هدف از پردازش خودکار متن آن است که نکات مهم با کمترین خطا استخراج "
        "شود و خواننده بتواند تصویری روشن از موضوع به دست آورد.",
        "در بخش دوم زمان رسیدگی به خرابی‌ها کاهش یافته است.",
    ]
    assert not any(sentence.startswith("شود و خواننده") for sentence in sentences)
    assert not any("مقدمه" in sentence for sentence in sentences)
    result = run(svc.summarize_async(text, "long", **FLAGS))
    assert all(line in sentences for line in result.splitlines())
    assert provider.calls == []


def test_v5_never_joins_across_two_blank_lines_or_markdown_exclusion():
    svc, _ = service()
    text = (
        "این عبارت ناتمام مانده است و باید تکمیل\n\n\n"
        "جمله جدید یک تصمیم رسمی را گزارش می‌کند.\n\n"
        "## خارج از محدوده\n"
        "بخش غیرمجاز در متن اصلی وجود دارد.\n"
        "## بخش فعلی\n"
        "اینجا قابلیت فعلی توصیف شده است."
    )
    sentences = [sentence for _, sentence in svc._source_sentence_candidates(text)]
    assert "جمله جدید یک تصمیم رسمی را گزارش می‌کند." in sentences
    assert "اینجا قابلیت فعلی توصیف شده است." in sentences
    assert not any("عبارت ناتمام" in sentence for sentence in sentences)
    assert not any("غیرمجاز" in sentence for sentence in sentences)


def test_v5_preserves_original_negation_across_pdf_wrapped_lines():
    svc, _ = service()
    text = (
        "برای مثال، افزایش مصرف الزاماً به معنای خرابی شبکه نیست و شاید\n\n"
        "به تغییر فصل یا افزایش تعداد مشترکان مربوط باشد.\n\n\n"
        "برای نمونه، جمله «احتمال نشتی وجود دارد» نباید به عبارت\n\n"
        "«نشتی تأیید شد» تبدیل شود؛ زیرا تغییر، سطح اطمینان را دگرگون می‌کند."
    )
    sentences = [sentence for _, sentence in svc._source_sentence_candidates(text)]
    assert "افزایش مصرف الزاماً به معنای خرابی شبکه نیست" in sentences[0]
    assert "شاید به تغییر فصل" in sentences[0]
    assert "نباید به عبارت «نشتی تأیید شد» تبدیل شود؛" in sentences[1]
    assert not any(sentence.startswith("«نشتی تأیید شد»") for sentence in sentences)


def test_v5_raw_source_work_budget_cannot_be_bypassed_by_normalization():
    svc, provider = service()
    # Whitespace normalization reduces this huge raw document to one sentence.
    source = "\n" * (svc._chunker.MAX_TEXT_CHARACTERS + 1) + (
        "در بخش دوم زمان رسیدگی به خرابی‌ها کاهش یافته است."
    )
    with pytest.raises(ChunkingLimitError, match="input exceeds chunking character budget"):
        run(svc.summarize_async(source, "long", **FLAGS))
    assert provider.calls == []
