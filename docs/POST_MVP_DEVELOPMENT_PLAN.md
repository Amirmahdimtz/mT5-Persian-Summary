# Post-MVP Development Plan — Summary Quality & Document Query

> **Project:** mT5 Persian Summarization Service  
> **Repository:** [Amirmahdimtz/mT5-Persian-Summary](https://github.com/Amirmahdimtz/mT5-Persian-Summary)  
> **Branch:** `main`  
> **Plan Version:** 1.0  
> **Created:** 2026-11-01  
> **Status:** Stage 9 completed (engineering baseline); Stage 10 quality acceptance deferred by user for development progression (Production NO-GO); Stage 11 completed (Development engineering verification); Stages 12–13 not started  
> **Architecture:** [Service_Architecture_Guide_FA.md](../Service_Architecture_Guide_FA.md)  
> **MVP Plan:** [IMPLEMENTATION_PLAN.md](../IMPLEMENTATION_PLAN.md)  
> **Implementation Record:** [IMPLEMENTATION_PROGRESS.md](IMPLEMENTATION_PROGRESS.md)

## 1. هدف و تصمیم نهایی

پس از تکمیل هشت مرحله MVP، فاز دوم در **پنج مرحله جدید (Stages 9–13)** اجرا می‌شود. دو هدف مورد توافق عبارت‌اند از:

1. افزایش **کیفیت، پوشش اطلاعات، وفاداری به واقعیت و کنترل طول** در خلاصه‌سازی عمومی متن و سند فارسی.
2. اضافه کردن یک قابلیت **مستقل و اختیاری** برای پرسیدن سؤال از سند یا دریافت خلاصه محدود به یک موضوع خاص، بدون الزام کاربران Endpointهای قبلی به ارسال `query`.

این سند **نقشه راه توسعه** است، نه گزارش پیاده‌سازی. وضعیت مراحل در جدول زیر به‌روزرسانی می‌شود؛ وضعیت آغازین آن‌ها `Not Started` بود. تکمیل هشت مرحله MVP یا Benchmark مرحله ۹ به معنی تأیید کیفیت معنایی یا وجود قابلیت Document Query نیست. مدارک بسته‌شدن Baseline مرحله ۹: [STAGE9_BASELINE_SIGNOFF.md](STAGE9_BASELINE_SIGNOFF.md).

### جدول مراحل و وابستگی‌ها

| Stage | عنوان | محور | وابستگی | خروجی اصلی | وضعیت |
| --- | --- | --- | --- | --- | --- |
| **9** | Quality Benchmark & Root-Cause Analysis | کیفیت خلاصه | MVP موجود | دیتاست و گزارش Baseline قابل تکرار | Completed (diagnostic baseline only) |
| **10** | General Summarization Quality Improvement | کیفیت خلاصه | 9 | Pipeline بهبودیافته با Benchmark مقایسه‌ای | Quality-limited; user accepted deferral for development progression (Production NO-GO) |
| **11** | Evidence-aware Extraction & Retrieval | Document Query | 9؛ اجزای استخراج موجود | بازیابی بخش‌های مرتبط همراه Source Location | Completed (Development engineering: 429 tests passed; 15/15 Recall@1 & Recall@3) |
| **12** | Document Query API & Answering | Document Query | 11؛ استفاده مجدد از اجزای Stage 10 در صورت نیاز | Endpoint مستقل برای `answer` و `focused_summary` | Not Started |
| **13** | Quality Evaluation, Hardening & Delivery | هر دو | 10 و 12 | تست End-to-End، معیارهای کیفی و مستندات تحویل | Not Started |

**Stage 10 experiment record:** [STAGE10_EXPERIMENT_V1.md](STAGE10_EXPERIMENT_V1.md) — v4 real-document Development gain did not pass frozen Synthetic gates (critical direction inversions and identical length tiers); v5 opt-in source-only extraction is a diagnostic experiment awaiting actual Windows verification and independent review. No Production GO.

**Stage 11 implementation record:** [STAGE11_RETRIEVAL_REPORT.md](STAGE11_RETRIEVAL_REPORT.md) — model-free structured TXT/PDF/DOCX extraction and Development-only lexical evidence ranking, without a Stage 12 HTTP endpoint. Windows verification is complete (85 targeted tests passed, 429 full-suite tests passed with 2 deprecation warnings, and 15/15 exact source-quote retrievals at both Recall@1 and Recall@3). Stage 10's existing quality threshold remains unmet; the user's approval only authorizes proceeding with development.

**ترتیب اجرایی پیش‌فرض:** `9 → 10 → 11 → 12 → 13`. پس از Stage 9، فعالیت‌های Stage 10 و طراحی Stage 11 از نظر فنی می‌توانند با هماهنگی مستقل شوند؛ برای Commitهای مستقیم روی `main`، تغییرات باید کنترل‌شده و بدون overwrite انجام شوند.

## 2. وضعیت واقعی MVP و مسئله شناخته‌شده

بر اساس مرور سورس `main` و ثبت پیشرفت قبلی در زمان ایجاد سند:

- Endpointهای فعلی: `POST /api/v1/summarization/text`، `/file` و `/files`.
- مدل فعلی: `nafisehNik/mt5-persian-summary` با revision پین‌شده `b575560ad967050e77a40f907abb1ebbeefb9a15`. جایگزینی آن تصمیم از پیش قطعی‌شده نیست.
- `TextChunkingService`: تقسیم بر اساس Tokenizer و حفظ پوشش متن نرمال‌شده؛ سقف‌های فعلی شامل ۱۰۰۰ توکن برای هر ورودی مدل، ۶۴ Chunk و ۲۰۰٬۰۰۰ کاراکتر برای مسیر متن است.
- `LongTextSummarizationService`: خلاصه‌سازی سلسله‌مراتبی با حداکثر ۶ سطح و ۱۲۸ فراخوانی مدل. بودجه طول فعلی از `max_output_tokens=120` مشتق شده و برای `short/medium/long` به‌ترتیب ۴۰/۸۰/۱۲۰ توکن است؛ **این مقدار سقف است، نه طول تضمین‌شده**.
- `Mt5ModelProvider`: Singleton در هر Process، بارگذاری Lazy، Inference غیرمسدودکننده Event Loop از طریق Worker Thread، کنترل Concurrency و Admission.
- آخرین گزارش تست ثبت‌شده پیش از این سند: **۲۶۶ تست موفق** در محیط کاربر و Docker HTTP E2E؛ این نتایج **Benchmark دقت خلاصه‌سازی نیستند** و اجرای دوباره در این مرحله انجام نشده است.
- شواهد مشکل: نمونه چندموضوعی بعضی موضوع‌ها را حذف کرده و جهت یک تغییر مربوط به آلودگی هوا را اشتباه بیان کرده است؛ برای یک PDF هشت‌صفحه‌ای با ۱۸٬۰۵۲ کاراکتر، خروجی `medium` و `long` هر دو ۱۱۳ کاراکتر و یکسان گزارش شده‌اند.
- استخراج TXT/PDF متنی/DOCX وجود دارد، ولی قرارداد فعلی `extract(content, filename) -> str`، موقعیت دقیق شاهد (صفحه/پاراگراف) را در خروجی حمل نمی‌کند.

**اصل مهم:** خطای ساختاری، مشکل بازیابی شواهد، نارسایی مدل یا محدودیت Generation باید در Stage 9 از هم تفکیک شوند؛ تعویض مدل یا Fine-tuning پیش‌فرض نیست.

## 3. محدوده و قواعد الزام‌آور

### 3.1 در محدوده

- ارزیابی کیفی تکرارپذیر روی اسناد فارسی، به‌خصوص صورت‌جلسه، گزارش و متن چندموضوعی.
- بهبود Chunking، حفظ پوشش اطلاعات، کنترل خلاصه‌های میانی، Generation و وفاداری خلاصه.
- بازیابی بخش‌های مرتبط با سؤال، پاسخ استخراجی به اطلاعات قابل استناد (مثل تاریخ، شخص، مسئول، مبلغ) و خلاصه موضوعی بر پایه شواهد.
- یک Endpoint جدید برای **یک سند در هر Request**؛ پشتیبانی از همان `.txt`، PDF متنی و `.docx`.
- نشانه‌گذاری منبع در پاسخ: `page` برای PDF در صورت قابل بازیابی بودن؛ `paragraph` یا `section` برای اسنادی که Page قابل اتکا ندارند.
- تست خودکار با Mock، ارزیابی مدل واقعی اختیاری، تست امنیت و مستندسازی API/Docker.

### 3.2 خارج از محدوده این پنج مرحله

- OCR، PDF اسکن‌شده، Database، Vector Database سرویس‌محور، ذخیره دائمی سند، Authentication، UI، Queue یا پردازش Background.
- جست‌وجو میان تمام اسناد تاریخی/کاربران؛ اتصال به یک Knowledge Base پایدار.
- تغییر اجباری Endpointهای MVP، حذف پشتیبانی از فرمت‌های فعلی یا الزام `query` در خلاصه‌سازی عمومی.
- تعویض مدل، افزودن Embedding بزرگ، Fine-tuning یا افزایش منابع GPU **بدون نتیجه Benchmark، بررسی License و تصمیم فنی ثبت‌شده**.
- تضمین صحت کامل پاسخ برای تمام اسناد واقعی.

### 3.3 معماری و سازگاری

مطابق `Service_Architecture_Guide_FA.md`:

- `Host → Application → Core → Infrastructure` حفظ شود.
- Controllerها Thin؛ Workflow در Service؛ Model/Tokenizer در Infrastructure Provider.
- Constructor DI و `@inject`؛ متدهای Async با پسوند `_async`؛ مسیر import از `src.*`.
- Auto Discovery با `src/application/{feature}/{feature}_controller.py`، کلاس پایان‌یافته به `Controller` و متد `api()`.
- عدم افزودن Interface/Layer/Repository غیرضروری؛ بدون DB در Scope حاضر.
- APIها و DTOهای فعلی Backward Compatible باقی بمانند؛ قرارداد موجود `DocumentExtractionService.extract` بدون شکستن Callerهای فعلی حفظ شود.
- همه Processing Boundها و Error Mappingهای امن فعلی برقرار بمانند. داده‌های اسناد به‌عنوان محتوای غیرقابل اعتماد تلقی شوند، نه دستور اجرایی.

## 4. Stage 9 — Quality Benchmark & Root-Cause Analysis

**هدف:** اندازه‌گیری و ریشه‌یابی مشکلات فعلی قبل از اعمال تغییر در الگوریتم.

**کارها:**

1. ایجاد مجموعه آزمون نسخه‌بندی‌شده با مجوز استفاده روشن: حداقل یک مجموعه شروع از اسناد کوتاه/بلند، خبر، صورت‌جلسه، گزارش، چندموضوعی، و نمونه‌های تاریخ/نام/عدد. در صورت فراهم شدن داده مناسب، هدف اولیه **۳۰ تا ۵۰ سند** و **حداقل ۱۰۰ سؤال برچسب‌خورده** برای فاز دوم است؛ این تعداد هدف تهیه داده است، نه ادعای وجود فایل.
2. تعریف خلاصه مرجع یا برچسب «واقعیت‌های ضروری» با مکان شواهد در متن؛ جداسازی مجموعه توسعه از مجموعه ارزیابی نهایی.
3. اندازه‌گیری `Fact Coverage`، `Unsupported Claim Rate`، `Date/Name/Number Consistency`، `Length Adherence`، نرخ تکرار، صحت ترتیب و حفظ موضوعات.
4. اجرا و ثبت Pipeline فعلی، Model ID/Revision، Generation Config، Dataset Version و شرایط CPU/Memory/Latency.
5. تفکیک خطاهای Extraction (خصوصاً RTL در PDF)، Chunk Boundary، Hierarchical Reduction و خود mT5. مقایسه متن استخراج‌شده با فایل اصلی، قبل از قضاوت درباره مدل.
6. ثبت معیار قبولی عددی Stage 10 و Stage 11/13 **پیش از Tune کردن**؛ پس از بررسی تعادل بین کیفیت، هزینه و داده مرجع.

**خروجی قابل تحویل:** Benchmark Runner/Fixtures، مستند متریک‌ها، Baseline Report و فهرست Root Causeهای اولویت‌بندی‌شده. محل دقیق کد/تست بر اساس ساختار فعلی Repository هنگام اجرای Stage تعیین می‌شود.

**Acceptance Criteria:**

- Benchmark روی مجموعه ثابت تکرارپذیر است؛ نمونه‌ها، تنظیمات و Expected Facts قابل بازبینی هستند.
- دست‌کم سه سناریوی مشکل واقعی فعلی (کوتاه/چندموضوعی/بلند) بازتولید یا با داده جایگزین معادل مستند می‌شوند؛ PDF هشت‌صفحه‌ای تنها اگر خود فایل مجاز و در دسترس باشد.
- گزارش تفاوت «عملکرد مدل» و «مشکل Extraction» را روشن کند؛ هیچ نتیجه بدون اجرای واقعی `Passed` گزارش نشود.
- آستانه‌ها، نمونه‌های کنترل و معیارهای Stop/Go مراحل بعد مستند شوند.

## 5. Stage 10 — General Summarization Quality Improvement

**هدف:** بهبود سنجش‌پذیر Endpointهای خلاصه‌سازی موجود بدون شکستن قرارداد آنها.

**کارها:**

1. بهینه‌سازی Boundaryهای Chunk با احترام به Paragraph/Section/Topic و Tokenizer Budget؛ حفظ ترتیب و پوشش کامل متن.
2. بازنگری Map/Reduce و خلاصه‌های میانی برای کاهش حذف حقایق مهم؛ جلوگیری از Recursion بی‌انتها یا عبور از Model Call Budget.
3. آزمایش کنترل‌شده `num_beams`، `length_penalty`، `repetition_penalty`، Decoder Length و Target Length. تنظیمات جدید باید در YAML/Config ثبت شوند؛ صرفاً افزایش `max_length` اصلاح کیفیت محسوب نمی‌شود.
4. در صورت نیاز، Evidence/Fact Preservation Check یا استخراج عناصر کلیدی قبل و بعد از تولید خلاصه با ریسک Hallucination کنترل‌شده.
5. مقایسه تغییرات روی همان Benchmark Stage 9، شامل زمان اجرا و حافظه؛ Rollback راحت به Config/Pipeline قبلی.
6. تنها در صورت ناکافی بودن نتایج، مقایسه مستند مدل جایگزین یا Fine-tuning به‌عنوان **پیشنهاد تصمیم بعدی**؛ انجام آنها خارج از Scope خودکار این Stage است.

**Acceptance Criteria:**

- متریک اصلی پوشش اطلاعات نسبت به Baseline به شکل قابل دفاع بهبود یابد؛ آستانه عددی از Stage 9 اخذ می‌شود.
- نرخ ادعاهای بی‌پشتوانه و خطاهای تاریخ/شخص/عدد بدتر نشود؛ اگر این شرط برقرار نیست، تغییر Quality قابل پذیرش نیست.
- `short/medium/long` روی نمونه‌های تعیین‌شده از نظر هدف و بودجه قابل تشخیص باشند؛ ادعای تضمین طول دقیق ممنوع.
- موردهای بلند و PDF چندموضوعی رفتار مستند داشته باشند؛ Truncation خاموش، Regression در Upload و اختلال در DI وجود نداشته باشد.
- Unit/Integration Testهای هدفمند و Regression Suite اجرا یا مانع دقیق ثبت شود.

## 6. Stage 11 — Evidence-aware Extraction & Retrieval

**هدف:** یافتن شواهد مرتبط **از متن اصلی سند**، نه از خلاصه عمومی که ممکن است اطلاعات حذف کرده باشد.

**کارها:**

1. ارائه خروجی ساخت‌یافته استخراج به‌صورت مسیر جدید یا متد تکمیلی بدون تغییر قرارداد `extract(...) -> str`؛ Segmentها شامل `text`، `source_location` و `document_order` باشند.
2. برای PDF شماره صفحه صحیح را در حد پشتیبانی Parser نگه داریم؛ برای TXT/DOCX Paragraph/Section Location قابل اتکا تولید شود. از اختراع شماره صفحه برای DOCX خودداری شود.
3. نرمال‌سازی فارسی برای Retrieval (اختلاف «ی/ي»، «ک/ك»، فاصله، نیم‌فاصله و شکل اعداد) بدون تغییر شواهد اصلی و بدون تخریب تاریخ/نام.
4. ایجاد Retriever ساده و قابل تست بر پایه واژه/عبارت و امتیازدهی؛ اگر Benchmark کمبود معنادار نشان داد، Hybrid Retrieval یا مدل Embedding فارسی/چندزبانه بررسی و در همان Stage با توجیه منابع و License اضافه شود.
5. طراحی Evidence Ranking، Chunk Overlap، Budget محدود و کنترل عدم یافتن/ابهام/تعارض بین شواهد.
6. برای سؤال‌هایی مثل «تاریخ جلسه» یا «مسئول پیگیری» به استخراج واقعیت مستند و ارجاع دقیق اولویت دهیم؛ پاسخ از Retrieval نباید تاریخ یا شخص ساخته‌شده داشته باشد.

**Acceptance Criteria:**

- سؤال‌های برچسب‌خورده درباره تاریخ، نام، وظیفه، عدد و موضوع بخش درست را با Source Location واقعی بازیابی کنند؛ معیار `Recall@K` و نتایج روی مجموعه Stage 9 ثبت شود.
- نمونه‌های بدون پاسخ `not_found` و شواهد متعارض `ambiguous` در Workflow قابل تشخیص باشند.
- Retriever در Unit Test به Load واقعی mT5 یا دانلود Embedding وابسته نباشد.
- استخراج و Uploadهای فعلی بدون Regression باقی بمانند؛ محرمانگی و بودجه حافظه کنترل شود.

## 7. Stage 12 — Document Query API & Answering

**هدف:** Feature مستقل و اختیاری برای پاسخ‌گویی یا خلاصه‌سازی موضوعی روی یک سند ورودی.

### 7.1 قرارداد پیشنهادی HTTP

`POST /api/v1/document_query/file` با `multipart/form-data`:

| Field | Type | Requirement | Behavior |
| --- | --- | --- | --- |
| `file` | File | Required | یک فایل TXT/PDF متنی/DOCX |
| `query` | String | Required | سؤال یا موضوع مشخص؛ Validation برای خالی نبودن و محدودیت طول |
| `mode` | Enum | Optional | `answer` (default) یا `focused_summary` |
| `summary_length` | Enum | Optional | `short` / `medium` (default) / `long`، فقط برای `focused_summary` معنادار |

برای `answer`، حقل `summary_length` در صورت ارسال می‌تواند طبق قرارداد نهایی رد شود یا نادیده گرفته شود؛ این تصمیم باید قبل از کدنویسی در DTO/Test تثبیت شود. پارامترهای اضافی باید صریحاً Validate شوند.

**Response پیشنهادی:**

```json
{
  "status": "found",
  "mode": "answer",
  "query": "تاریخ جلسه بعدی چه زمانی است؟",
  "answer": "جلسه بعدی در ۱۵ آبان برگزار می‌شود.",
  "evidence": [
    {
      "location_type": "page",
      "page": 3,
      "paragraph": null,
      "text": "جلسه بعدی در تاریخ ۱۵ آبان برگزار خواهد شد."
    }
  ]
}
```

این پاسخ نمونه **ساختگی قراردادی** است؛ تاریخ یا Page واقعی تنها پس از پردازش سند تعیین می‌شود. در حالت `focused_summary` متن `answer` حاوی خلاصه موضوعی مستند است. اگر دلیل کافی در سند نیست: `status="not_found"`، `answer=null`، `evidence=[]`. در تضادهای حل‌نشده `status="ambiguous"` و شواهد متعارض گزارش شود.

### 7.2 جریان پردازش

`Upload Validation → Structured Text Extraction → Evidence Retrieval → Evidence Validation → Answer Extraction / Focused Summarization → Source-grounded Response`.

- `mode=answer`: اولویت با Extractive Answer / Structured Fact Extraction است؛ mT5 خبرمحور به‌تنهایی مدل Q&A قابل اعتماد فرض نشود.
- `mode=focused_summary`: تنها شواهد مرتبط به Pipeline تولید خلاصه داده شوند؛ متن تولیدشده در صورت ادعای واقعیت نیاز به بررسی در برابر شواهد دارد.
- Pipeline عمومی بدون `query` همچنان به شکل موجود کار می‌کند؛ Endpoints قبلی تغییر اجباری ندارند.

### 7.3 فایل‌ها و Feature Boundary پیشنهادی

```text
src/
  application/document_query/
    document_query_controller.py
    dtos/document_query_dto.py
  core/services/document_query/
    document_query_service.py
    retrieval_service.py
  infrastructure/ml/
    mt5_model_provider.py          # reuse, not duplicate
    [optional embedding provider]  # only if benchmark justifies
```

فایل‌های جدید/تغییر یافته بالا **پیشنهادی** هستند و وجود آنها مفروض نیست؛ هنگام اجرای Stage 12 ساختار و فایل‌های واقعی بررسی شوند. برای Validation آپلود، در صورت نیاز کد مشترک موجود به Helper قابل استفاده مجدد منتقل شود؛ Import کردن توابع Private یک Controller از Controller دیگر یا کپی کامل Validation ممنوع است.

**Acceptance Criteria:**

- Route جدید از Auto Discovery ثبت شده و در Swagger قابل تست باشد؛ Form Fields/Response DTO دقیق و Validation شده باشند.
- برای `answer` تاریخ/شخص/عدد فقط با شواهد معتبر و قابل ارجاع پاسخ داده شود؛ در نبود شواهد پاسخ ساخته نشود.
- برای `focused_summary` تنها موضوع مرتبط پوشش داده شود؛ هیچ `query` برای Endpointهای قبلی لازم نباشد.
- `found`، `not_found`، `ambiguous`، ورودی نامعتبر، فایل بزرگ/خراب و عدم دسترسی مدل Status/HTTP مناسب و امن داشته باشند.
- Unit و API Integration Test با Mock و در صورت دسترسی تست مدل واقعی اضافه شوند.

## 8. Stage 13 — Quality Evaluation, Hardening & Final Delivery

**هدف:** تحویل کیفیت قابل سنجش، مستند و قابل اجرا برای هر دو قابلیت.

**کارها:**

1. اجرای Benchmark ثابت Stage 9 روی خروجی Stage 10؛ مقایسه دقیق قبل/بعد و ثبت ناکامی‌ها.
2. ارزیابی Stage 11/12 با `Recall@K`، `Answer Exact Match` برای اطلاعات قطعی، `Evidence Support Rate`، `No-answer Accuracy`، سناریوهای Ambiguous و Focused Coverage.
3. اجرای Unit/Integration/HTTP E2E برای متن، TXT، PDF متنی، DOCX، متن بلند، تاریخ/شخص/عدد، بدون نتیجه و چند شاهد متعارض.
4. تست Bounding حافظه و Concurrency، Admission، Timeouts، Cancellation و جلوگیری از Blocking Event Loop. از ادعای Cancellation قطعی در Worker Thread خودداری شود.
5. Validation اندازه `query`، محدودیت فایل/متن، ایمنی Parser، جلوگیری از نشت اطلاعات سند در Logging و دفاع در برابر Prompt Injection داخل سند (متن سند **Instruction** محسوب نمی‌شود).
6. به‌روزرسانی README، Swagger، Configuration، Docker و Progress؛ بررسی اجرای فعلی Windows و Docker روی منابع واقعی و حفظ Compatibility.
7. مستندسازی محدودیت‌ها، عملکرد اندازه‌گیری‌شده، تصمیم‌های مربوط به Embedding/Model و پیشنهاد Backlog.

**Acceptance Criteria:**

- تمام Testهای سریع جدید و Regression قبلی در محیط در دسترس Pass شوند؛ برای تست اجرا‌نشده ادعای موفقیت نشود.
- Benchmark نهایی، تغییر کیفیت، نقاط ضعف و متریک‌های Retrieval/Answer قابل بازتولید و مقایسه با Baseline باشند.
- End-to-End برای هر دو `mode` با سند واقعی/نمونه مجاز و Evidence Location قابل تأیید اجرا شود.
- سه Endpoint اصلی بدون تغییر ناسازگار بمانند؛ Swagger و مستندات اجرای محلی و Docker به‌روز باشند.
- Memory/Latency و Known Issues با مقدار واقعی یا `Not Measured` گزارش شوند؛ صرف پاسخ HTTP 200 نشانه دقت معنایی نیست.

## 9. سیاست Evaluation و Stop/Go

### Metricها

| Metric | تعریف عملیاتی | استفاده |
| --- | --- | --- |
| Fact Coverage | نسبت واقعیت‌های مهم مرجع که در خلاصه حفظ شده‌اند | سنجش Recall خلاصه |
| Unsupported Claim Rate | نسبت ادعاهای خلاصه که شاهد کافی در متن ندارند | Faithfulness |
| Entity/Number/Date Consistency | درستی نام‌ها، مقادیر، تاریخ‌ها و جهت تغییرات | Factual Accuracy |
| Length Adherence | نسبت و پراکندگی طول واقعی به بودجه/سطح درخواست | کنترل Output |
| Retrieval Recall@K | درصد سؤال‌های پاسخ‌دار که شواهد درست در K نتیجه اول هستند | ارزیابی جست‌وجو |
| Evidence Support Rate | درصد پاسخ‌های `found` که شواهد انتخابی از ادعای آنها پشتیبانی می‌کند | Grounding |
| No-answer Accuracy | تشخیص درست `not_found` در نمونه‌های فاقد پاسخ | جلوگیری از ساختگی‌گویی |
| p50/p95 Latency & Peak RAM | زمان/حافظه با workload و سخت‌افزار ثبت‌شده | هزینه عملیاتی |

**مقادیر عددی هدف و Dataset Split در پایان Stage 9 تعیین و Freeze می‌شوند** تا Acceptance Criteria با تغییر نمونه‌ها یا Tune روی Test Set دست‌کاری نشوند. هدف مقدماتی Retrieval: نزدیک شدن به `Recall@5 ≥ 0.90` روی مجموعه ارزیابی واقعی، در صورت سازگاری با Baseline و هزینه؛ **این عدد نه نتیجه فعلی است و نه معیار قطعی قبل از Stage 9**.

**قانون تصمیم:** اگر کیفیت خلاصه بهتر شود ولی میزان ادعاهای ساختگی افزایش یابد، Stage 10 `Completed` نمی‌شود. اگر Retriever روی تاریخ/اسامی پاسخ غیرمستند برگرداند، Stage 12 `Completed` نمی‌شود. اگر مدل فعلی یا معماری انتخابی مانع رسیدن به Threshold شود، شواهد و پیشنهاد مدل/Scope جدید ثبت و وضعیت `Blocked` اعلام شود؛ Feature ناقص به‌عنوان Completed منتشر نشود.

## 10. امنیت، مصرف منابع و عملیاتی بودن

- حفظ سقف‌های موجود: هر فایل تا **20 MiB**؛ Upload مجموع پیش‌فرض **32 MiB**؛ یک Worker CPU به‌صورت پیش‌فرض و ظرفیت Inference محدود در هر Process. افزودن ویژگی جدید نباید این Guardها را دور بزند.
- Query و Evidenceهای خام ممکن است داده محرمانه داشته باشند؛ در Logging، Exception و Telemetry خام قرار نگیرند.
- سند آپلودشده ورودی غیرقابل اعتماد است؛ Embedded Instructions نباید Workflow یا Policy سیستم را تغییر دهند.
- از ذخیره دائمی فایل/Embedding/Cache اشتراکی کاربر در این Scope خودداری شود. در صورت به‌کارگیری Embedding، Lifecycle/Lock/Memory باید سنجیده شود.
- حد CPU/GPU، هزینه Inference، زمان پاسخ، Cancellation و Peak RAM به‌طور عملی اندازه‌گیری و با هر تغییر معنی‌دار بررسی شود.
- Dependency تازه فقط با نیاز اثبات‌شده، نسخه سازگار، License و ارزیابی Supply Chain اضافه شود.

## 11. قرارداد اجرای هر Stage در چت مستقل

برای درخواست «مرحله N را شروع کن» که `N∈{9,10,11,12,13}` است، این ترتیب الزام‌آور است:

1. بررسی تازه `Service_Architecture_Guide_FA.md`، `IMPLEMENTATION_PLAN.md`، `docs/POST_MVP_DEVELOPMENT_PLAN.md`، `docs/IMPLEMENTATION_PROGRESS.md` و آخرین سورس `main` GitHub.
2. بررسی آخرین Commit و Write Permission؛ تشخیص وضعیت Stageهای قبلی؛ عدم فرض وجود Feature از متن Plan.
3. پیاده‌سازی **فقط Stage خواسته‌شده** با Minimal Change؛ تست‌های مرتبط، Security و Error Handling.
4. اجرای Compile/Imports/Testهای قابل اجرا و تفکیک `Passed`/`Failed`/`Not Run`.
5. به‌روزرسانی `docs/IMPLEMENTATION_PROGRESS.md` با Stage/Status، Changed Files، Technical Decisions، Dependencies، Tests، Known Issues، Commit SHA (اگر در تاریخچه قابل ثبت است) و Next Stage Readiness.
6. Commit روی `main` با پیام انگلیسی مناسب و تأیید SHA؛ بدون Force Push، حذف مخرب، overwrite تغییرات هم‌زمان یا ثبت Secret.
7. پاسخ پایانی شامل Implementation Summary، GitHub Status، Setup/Test دقیق برای Windows PowerShell و در صورت نیاز Linux/macOS، Verification و Next Step.

**Definition of Done:** Stage فقط در صورت تحقق Acceptance Criteria و ثبت نتیجه واقعی تست/Commit، `Completed` می‌شود. صرف نوشتن کد یا Commit بدون کیفیت اندازه‌گیری‌شده کافی نیست.

## 12. فایل‌های مرجع و نحوه استفاده

- `Service_Architecture_Guide_FA.md`: قرارداد غیرقابل‌نقض معماری و DI.
- `IMPLEMENTATION_PLAN.md`: محدوده و تاریخچه نقشه هشت‌مرحله‌ای MVP؛ **مراحل ۱–۸ بازنویسی نمی‌شوند**.
- `docs/IMPLEMENTATION_PROGRESS.md`: وضعیت اجرایی و شواهد تست/Commit؛ باید هنگام هر Stage جدید به‌روزرسانی شود.
- `docs/POST_MVP_DEVELOPMENT_PLAN.md`: نقشه راه پذیرفته‌شده فاز دوم (همین سند).

### درخواست نمونه برای شروع

> «مرحله ۹ — Quality Benchmark & Root-Cause Analysis را مطابق `docs/POST_MVP_DEVELOPMENT_PLAN.md` شروع کن. ابتدا آخرین سورس GitHub و اسناد معماری/Progress را بررسی کن؛ فقط Stage 9 را پیاده‌سازی، تست، ثبت Progress و Commit روی `main` انجام بده و دستورات دقیق تست محلی را ارائه کن.»

**نتیجه برنامه:** **۵ مرحله پس از MVP (۹ تا ۱۳)**، با دو خروجی مستقل: کیفیت قابل سنجش بهتر برای خلاصه عمومی و Endpoint مجزای Document Query با شواهد و مدیریت «پاسخی یافت نشد».
