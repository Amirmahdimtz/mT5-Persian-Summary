"""Explicit opt-in, real-model smoke test: python -m src.infrastructure.ml.smoke_mt5_model."""

from src.infrastructure.di.bootstrap import bootstrap_di
from src.infrastructure.di.inject import resolve
from src.infrastructure.ml.mt5_model_provider import Mt5ModelProvider


def main() -> None:
    bootstrap_di()
    provider = resolve(Mt5ModelProvider)
    text = (
        "سازمان هواشناسی اعلام کرد که در روزهای آینده در مناطق شمالی کشور "
        "بارش باران پیش‌بینی می‌شود. مسئولان از شهروندان خواستند هنگام سفر "
        "احتیاط کنند و آخرین اطلاعیه‌های هواشناسی را دنبال کنند."
    )
    summary = provider.summarize(text)
    assert summary and summary.strip(), "mT5 returned an empty summary"
    print("Generated summary:", summary)


if __name__ == "__main__":
    main()
