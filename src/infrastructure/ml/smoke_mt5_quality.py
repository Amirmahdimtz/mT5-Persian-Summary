"""Optional real-model Persian quality smoke; excluded from pytest."""

from __future__ import annotations

import argparse
import asyncio
import re

from src.core.services.summarization.long_text_summarization_service import (
    LongTextSummarizationService,
)
from src.infrastructure.di.bootstrap import bootstrap_di
from src.infrastructure.di.inject import resolve


SAMPLES = {
    "short": (
        "سازمان هواشناسی اعلام کرد که در روزهای آینده بارش باران در استان‌های شمالی "
        "افزایش می‌یابد. کارشناسان به رانندگان توصیه کردند شرایط جاده‌ها را بررسی کنند."
    ),
    "long": (
        "وزارت آموزش و پرورش برنامه جدیدی برای بهبود دسترسی دانش‌آموزان به منابع "
        "آموزشی دیجیتال معرفی کرد. این برنامه شامل آموزش معلمان، ارتقای زیرساخت "
        "مدارس و ارزیابی دوره‌ای کیفیت آموزش است. مسئولان تأکید کردند اجرای "
        "برنامه به صورت مرحله‌ای خواهد بود و مدارس مناطق کم‌برخوردار اولویت دارند. "
    ) * 18,
    "multitopic": (
        "شهرداری اعلام کرد تعداد اتوبوس‌های برقی در مسیرهای پرتردد افزایش پیدا می‌کند. "
        "هدف این برنامه کاهش آلودگی هوا و کاهش زمان انتظار شهروندان است.\n\n"
        "در حوزه سلامت، مسئولان از افتتاح دو درمانگاه جدید و افزایش ساعات ارائه "
        "خدمات خبر دادند. این مراکز در محله‌هایی با دسترسی کمتر فعالیت خواهند کرد.\n\n"
        "در بخش آموزش، دانشگاه‌ها برای توسعه آزمایشگاه‌های هوش مصنوعی تفاهم‌نامه "
        "همکاری امضا کردند. آموزش دانشجویان و پژوهش‌های مشترک در اولویت قرار دارد."
    ),
}


async def smoke_async(name: str) -> None:
    bootstrap_di()
    service = resolve(LongTextSummarizationService)
    names = list(SAMPLES) if name == "all" else [name]
    for label in names:
        source = SAMPLES[label]
        result = await service.summarize_async(source, "medium")
        nonempty = bool(result.strip())
        has_persian = bool(re.search(r"[\u0600-\u06ff]", result))
        punctuation_only = not bool(re.search(r"\w", result, flags=re.UNICODE))
        severe_compression = len(result) < max(12, len(source) // 100)
        print(f"{label}: source_chars={len(source)} summary_chars={len(result)}")
        print(f"summary: {result}")
        print(
            f"checks: nonempty={nonempty}, persian={has_persian}, "
            f"punctuation_only={punctuation_only}, "
            f"very_short_relative_to_source={severe_compression}"
        )
        if not nonempty or not has_persian or punctuation_only:
            raise RuntimeError(f"Unusable Persian summary for {label}")
        # Length ratio is a quality warning, not a pass/fail correctness metric.


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", choices=(*SAMPLES, "all"), default="all")
    args = parser.parse_args()
    asyncio.run(smoke_async(args.sample))


if __name__ == "__main__":
    main()
