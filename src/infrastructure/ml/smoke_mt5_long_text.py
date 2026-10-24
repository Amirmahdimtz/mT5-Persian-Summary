"""Opt-in CPU-heavy Stage 4 smoke (never collected by pytest)."""

from __future__ import annotations

import asyncio

from src.core.services.summarization.long_text_summarization_service import (
    LongTextSummarizationService,
)
from src.core.services.summarization.text_chunking_service import TextChunkingService
from src.infrastructure.di.bootstrap import bootstrap_di
from src.infrastructure.di.inject import resolve
from src.infrastructure.ml.mt5_model_provider import Mt5ModelProvider


async def main_async() -> None:
    bootstrap_di()
    provider = resolve(Mt5ModelProvider)
    chunker = resolve(TextChunkingService)
    service = resolve(LongTextSummarizationService)
    paragraph = (
        "پژوهشگران اعلام کردند که سامانه‌های جدید می‌توانند در تحلیل اسناد "
        "فارسی کمک کنند. حفظ ترتیب اطلاعات و ارزیابی دقیق نتایج اهمیت دارد. "
        "استفاده مسئولانه از این فناوری به بررسی کیفیت داده‌ها نیاز دارد.\n\n"
    )
    document = paragraph
    for _ in range(6):
        if len(await asyncio.to_thread(chunker.chunk, document)) >= 2:
            break
        document += document
    else:
        raise AssertionError("smoke document did not exceed one model input")

    summary = await service.summarize_async(document, "medium")
    budget = service.output_token_budget("medium")
    if not summary.strip() or provider.count_input_tokens(summary) > budget:
        raise AssertionError("smoke output is empty or exceeds requested budget")
    print("Input characters:", len(document))
    print("Summary token budget:", budget)
    print("Summary:", summary)


if __name__ == "__main__":
    asyncio.run(main_async())
