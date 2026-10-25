# خلاصه‌سازی متن و اسناد فارسی با mT5

**Persian Document Summarization REST API · FastAPI · mT5 · Docker**

این پروژه متن فارسی یا فایل‌های `TXT`، `PDF` متنی و `DOCX` را دریافت می‌کند و با مدل [`nafisehNik/mt5-persian-summary`](https://huggingface.co/nafisehNik/mt5-persian-summary) یک **خلاصه فارسی** برمی‌گرداند. امکان ارسال چند فایل در یک درخواست وجود دارد و **برای هر فایل خلاصه جداگانه** تولید می‌شود.

> **وضعیت: MVP قابل اجرا و تست‌شده.** اجرای موفق API به معنی صحیح‌بودن همه خلاصه‌ها نیست. مدل ممکن است نکات مهم را حذف کند، اطلاعات را اشتباه بازگو کند یا برای اسناد بلند خلاصه‌ای بیش‌ازحد کوتاه بسازد. **قبل از استفاده مدیریتی یا سازمانی، خلاصه را با سند اصلی تطبیق دهید.**

## برای شروع چه چیزی لازم است؟

| مورد | توضیح |
| --- | --- |
| سریع‌ترین اجرا | Docker Desktop / Docker Engine و Image آماده در GHCR |
| بدون Docker | Python 3.12 و نصب `requirements.txt` |
| سخت‌افزار | مدل فعلاً روی **CPU** اجرا می‌شود؛ برای Docker حدود **8 GiB حافظه در دسترس** در نظر بگیرید (برآورد اولیه، نه اندازه‌گیری Peak RAM) |
| اینترنت | برای دریافت Image و دانلود اولیه وزن‌های مدل از Hugging Face، مگر اینکه فایل‌های موردنیاز قبلاً Cache شده باشند |
| کار با سرویس | Swagger در `/docs` یا درخواست HTTP به REST API |
| فرمت‌های مجاز | `.txt` با UTF-8، `.pdf` دارای متن قابل استخراج، `.docx`؛ فایل اسکن‌شده/OCR پشتیبانی نمی‌شود |

**مسیر پیشنهادی:** اگر فقط می‌خواهید مدل را امتحان کنید، بخش «اجرای سریع با Docker» را انجام دهید؛ نیازی به نصب Python یا کلون‌کردن Repository نیست.

## ۱. اجرای سریع با Docker (پیشنهادی)

Image آماده در GitHub Container Registry قرار دارد؛ به ساخت محلی Docker Image احتیاج ندارید. روی **همان کامپیوتری** که می‌خواهید API را امتحان کنید، Docker را روشن و در PowerShell اجرا کنید:

```powershell
docker pull ghcr.io/amirmahdimtz/mt5-persian-summary:stage8

docker volume create mt5_hf_cache

docker run -d --name mt5-persian-summary --init --memory 8g --cpus 2 --pids-limit 256 --security-opt no-new-privileges -p 127.0.0.1:8002:8000 -v mt5_hf_cache:/home/app/.cache/huggingface -e env_type=production ghcr.io/amirmahdimtz/mt5-persian-summary:stage8
```

- `8002` پورت **کامپیوتر شما** و `8000` پورت **داخل Container** است؛ این عدد را در تمام نمونه‌های Docker همین راهنما استفاده کرده‌ایم.
- `127.0.0.1` یعنی سرویس فقط از کامپیوتر میزبان قابل دسترسی است؛ لینک آن روی سیستم همکار یا گوشی دیگر کار نمی‌کند.
- Volume با نام `mt5_hf_cache` وزن‌های دانلودشده را بین اجرای مجدد Container حفظ می‌کند.
- Image وزن‌های mT5 را داخل خود ندارد. **اولین درخواست واقعی خلاصه‌سازی** ممکن است برای دانلود Checkpoint حدود ۱٫۲ گیگابایتی و بارگذاری مدل زمان‌بر باشد.
- اگر Container با همین نام قبلاً ساخته شده و متوقف است، به‌جای `docker run` از `docker start mt5-persian-summary` استفاده کنید؛ اگر فعال است نیازی به ساخت مجدد نیست.

بررسی وضعیت:

```powershell
docker ps --filter name=mt5-persian-summary
docker inspect --format '{{json .State.Health}}' mt5-persian-summary
curl.exe -i http://127.0.0.1:8002/api/v1/health
```

پس از آماده‌شدن سرویس انتظار می‌رود `healthy` و پاسخ زیر را ببینید:

```json
{"status":"ok"}
```

**توجه:** Health فقط زنده‌بودن HTTP را نشان می‌دهد و تضمین نمی‌کند مدل دانلود یا آماده Inference شده باشد. بارگذاری مدل با نخستین درخواست خلاصه‌سازی بررسی می‌شود.

برای بازکردن Swagger در مرورگر ویندوز، **این دستور** را در PowerShell اجرا کنید:

```powershell
Start-Process "http://127.0.0.1:8002/docs"
```

یا آدرس `http://127.0.0.1:8002/docs` را **در نوار آدرس مرورگر** وارد کنید؛ URL را به‌تنهایی مثل یک فرمان در PowerShell ننویسید.

## ۲. اولین تست در Swagger، بدون کدنویسی

در صفحه `http://127.0.0.1:8002/docs` سه عملیات اصلی می‌بینید:

| Endpoint | چه کاری انجام می‌دهد؟ | ورودی |
| --- | --- | --- |
| `POST /api/v1/summarization/text` | خلاصه‌کردن یک متن فارسی | JSON با `text` و `summary_length` |
| `POST /api/v1/summarization/file` | خلاصه‌کردن **یک فایل** | انتخاب فایل و طول خلاصه |
| `POST /api/v1/summarization/files` | خلاصه‌کردن **چند فایل جداگانه** | چند فایل و طول خلاصه |

### تست متن

۱. بخش `POST /api/v1/summarization/text` را باز و روی **Try it out** کلیک کنید.
۲. متن زیر را در `Request body` بگذارید.
۳. روی **Execute** کلیک کنید و `Response body` را ببینید.

```json
{
  "text": "سازمان هواشناسی اعلام کرد که بارش باران در روزهای آینده در مناطق شمالی کشور افزایش می‌یابد. کارشناسان توصیه کردند رانندگان پیش از سفر وضعیت جاده‌ها را بررسی کنند و به هشدارهای هواشناسی توجه داشته باشند.",
  "summary_length": "medium"
}
```

در صورت موفقیت، HTTP `200` و فیلد `summary` برمی‌گردد. متن داخل `summary` خروجی مدل است؛ مقدار آن از قبل ثابت یا تضمین‌شده نیست.

### تست یک PDF یا Word

۱. `POST /api/v1/summarization/file` را باز کنید و **Try it out** را بزنید.
۲. در `file` روی **Choose File** بزنید و یک فایل `TXT`، `PDF` متنی یا `DOCX` انتخاب کنید.
۳. `summary_length` را روی `medium` بگذارید و **Execute** را بزنید.
۴. در پاسخ، `success: true` و `summary` را بررسی کنید.

**PDF متنی** فایلی است که بتوانید نوشته‌های داخل آن را انتخاب/کپی کنید. PDF صرفاً تصویری، OCR ندارد و در این MVP پردازش نمی‌شود.

### تست چند فایل

در `POST /api/v1/summarization/files` از **Try it out** استفاده کنید و چند فایل انتخاب کنید. خروجی دارای `results`، `succeeded` و `failed` است؛ هر آیتم نتیجه فایل خودش را دارد. این عملیات **یک خلاصه مشترک از همه فایل‌ها** تولید نمی‌کند. حتی اگر HTTP `200` باشد، ممکن است بعضی فایل‌ها `success: false` داشته باشند؛ همه آیتم‌ها را بررسی کنید.

## ۳. طول خلاصه: short، medium، long

`summary_length` مقدار اختیاری دارد و پیش‌فرض آن `medium` است:

| مقدار | سقف توکن تولید مدل برای هر فراخوانی |
| --- | ---: |
| `short` | 40 |
| `medium` | 80 |
| `long` | 120 |

**این اعداد سقف هستند، نه تعداد کلمات و نه طول تضمین‌شده خروجی.** مدل ممکن است زودتر تولید را تمام کند و حتی در هر سه حالت خروجی یکسانی بدهد. برای یک PDF آزمایشی هشت‌صفحه‌ای با **۱۸٬۰۵۲ کاراکتر ورودی**، هر دو حالت `medium` و `long` خلاصه‌ای **یکسان و تنها ۱۱۳ کاراکتری** تولید کردند. بنابراین تغییر مقدار به `long` الزاماً مشکل کوتاه‌بودن خلاصه سند بلند را رفع نمی‌کند.

## ۴. استفاده از API بدون Swagger

آدرس پایه Docker در این راهنما: `http://127.0.0.1:8002`.

### PowerShell: ارسال متن فارسی

```powershell
$body = @{
    text = 'سازمان هواشناسی از افزایش بارش باران در شمال کشور خبر داد و به رانندگان هشدار داد.'
    summary_length = 'medium'
} | ConvertTo-Json -Compress

Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8002/api/v1/summarization/text' -ContentType 'application/json; charset=utf-8' -Body ([System.Text.Encoding]::UTF8.GetBytes($body))
```

### PowerShell: ارسال یک فایل

فایل `sample.pdf` باید واقعاً در پوشه فعلی وجود داشته باشد؛ نام آن را متناسب با فایل خود تغییر دهید:

```powershell
curl.exe -F 'file=@sample.pdf;type=application/pdf' -F 'summary_length=medium' http://127.0.0.1:8002/api/v1/summarization/file
```

### PowerShell: ارسال چند فایل

```powershell
curl.exe -F 'files=@sample.txt;type=text/plain' -F 'files=@sample.docx;type=application/vnd.openxmlformats-officedocument.wordprocessingml.document' -F 'summary_length=long' http://127.0.0.1:8002/api/v1/summarization/files
```

**نکته:** برای درخواست `multipart/form-data` با `curl -F`، هدر `Content-Type` را دستی تنظیم نکنید؛ `curl` آن را به‌همراه Boundary می‌سازد.

### Linux/macOS: نمونه با curl

پس از اجرای Container روی همان میزبان (با همان Port Mapping):

```bash
curl --fail-with-body -H 'Content-Type: application/json; charset=utf-8' \
  -d '{"text":"بارندگی در شمال کشور افزایش می‌یابد و رانندگان باید به هشدارهای جاده‌ای توجه کنند.","summary_length":"medium"}' \
  http://127.0.0.1:8002/api/v1/summarization/text

curl --fail-with-body -F 'file=@sample.txt;type=text/plain' -F 'summary_length=medium' \
  http://127.0.0.1:8002/api/v1/summarization/file
```

### معنی پاسخ‌ها

- در `/text` فیلدهای اصلی `summary`، `summary_length`، `input_characters` و `output_characters` هستند.
- در `/file` فیلدهای `filename`، `success`، `summary`، `error_code` و `error_message` نیز وجود دارند.
- در `/files`، آرایه `results` و تعداد `succeeded` و `failed` را بررسی کنید.
- `input_characters` تعداد کاراکتر متن ورودی استخراج‌شده و `output_characters` تعداد کاراکتر خلاصه است؛ این مقادیر **شاخص صحت معنایی** نیستند.

## ۵. مدل چیست و پروژه چگونه کار می‌کند؟

- **مدل انتخابی:** [`nafisehNik/mt5-persian-summary`](https://huggingface.co/nafisehNik/mt5-persian-summary)، با Revision ثابت `b575560ad967050e77a40f907abb1ebbeefb9a15`. مدل از خانواده **mT5** با معماری **Encoder–Decoder Transformer** است و طبق توضیحات منتشرکننده برای خلاصه‌سازی اخبار فارسی Fine-tune شده است.
- **آموزش مدل:** این Repository مدل را از ابتدا آموزش نمی‌دهد و خودش Fine-tuning انجام نمی‌دهد؛ مدل آماده را در سرویس FastAPI به کار می‌گیرد. وزن‌های FP32 حدود **۱٫۲ GB** حجم دارند و تعداد پارامترها تقریباً **۳۰۰ میلیون** برآورد شده، نه شمارش قطعی.
- **جریان پردازش:** `HTTP request → Text extraction (for files) → Token-aware chunking → Hierarchical summarization (for long inputs) → mT5 inference → JSON response`.
- **متن بلند:** متن‌های بلند بر اساس توکن تقسیم می‌شوند؛ قطعه‌ها خلاصه شده و در صورت نیاز خلاصه‌های میانی دوباره ترکیب/خلاصه می‌شوند. محدودیت‌های پردازشی ممکن است در متن‌های بسیار بزرگ به خطای صریح منجر شوند.
- **نحوه اجرا:** بارگذاری مدل به‌صورت Lazy و یک‌بار در هر Process انجام می‌شود؛ نسخه Docker روی **CPU و یک Uvicorn worker** تنظیم شده است.
- **Tokenizer و تولید:** `SentencePiece` و Hugging Face `Transformers`؛ تنظیمات فعلی `num_beams=2`، `do_sample=False`، `early_stopping=True` و سقف ورودی مدل **۱۰۰۰ توکن در هر قطعه** است.
- **مجوز مدل:** Model Card مجوز **MIT** را اعلام می‌کند؛ حقوق داده‌های آموزش و مجوز بازنشر کد این Repository باید مستقل بررسی شوند. در Revision فعلی Repository، فایل `LICENSE` جداگانه وجود ندارد.

پیکربندی اصلی: `src/host/res/appsettings.yaml`؛ محیط توسعه: `src/host/res/appsettings.development.yaml`. این فایل‌ها منبع واقعی تنظیمات مدل هستند؛ نام‌هایی مثل `MODEL_ID` را به‌عنوان Environment Variable پشتیبانی‌شده فرض نکنید.

## ۶. نصب و اجرای پروژه از سورس (برای توسعه‌دهنده‌ها)

اگر می‌خواهید به‌جای Image آماده، سورس را اجرا یا تغییر دهید، Repository را Clone کنید.

**Windows PowerShell / Python 3.12:**

```powershell
git clone https://github.com/Amirmahdimtz/mT5-Persian-Summary.git
cd mT5-Persian-Summary
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install 'torch>=2.6,<3.0' --index-url https://download.pytorch.org/whl/cpu
python -m pip install -r requirements.txt
python -m pip check
$env:env_type = 'development'
python -m uvicorn src.host.app:app --host 127.0.0.1 --port 8001 --workers 1
```

**Linux/macOS:**

```bash
git clone https://github.com/Amirmahdimtz/mT5-Persian-Summary.git
cd mT5-Persian-Summary
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip check
export env_type=development
python -m uvicorn src.host.app:app --host 127.0.0.1 --port 8001 --workers 1
```

در Linux CPU ممکن است نصب اولیه PyTorch از Index اختصاصی CPU مثل Dockerfile مناسب‌تر باشد؛ برای macOS باید نسخه پشتیبانی‌شده PyTorch همان سیستم نصب شود. برای اجرای توسعه‌ای Swagger در `http://127.0.0.1:8001/docs` باز می‌شود، نه پورت Docker یعنی `8002`.

برای اجرای Compose (روش جایگزین و نیازمند Build محلی):

```powershell
docker compose up --build -d
docker compose ps
docker compose logs --tail 100 summarizer
docker compose down
```

`compose.yaml` پورت میزبان **8000** و Volume مجزای `hf_cache` دارد. اجرای واقعی Compose به‌طور مستقل تأیید نشده است. دانلود Wheel لینوکس PyTorch از CDN روی بعضی شبکه‌ها کند یا ناموفق بوده؛ **برای اولین استفاده، Image آماده GHCR را ترجیح دهید**. Workflow ساخت Image در `.github/workflows/docker-image.yml` دستی است و خودکار با هر Push اجرا نمی‌شود.

## ۷. محدودیت‌ها و خطاهای رایج

| محدودیت | مقدار یا رفتار |
| --- | --- |
| متن مستقیم | ۱ تا **۲۰۰٬۰۰۰ کاراکتر** |
| هر فایل | حداکثر **20 MiB** |
| چند فایل | از **۱ تا ۳۲** فایل؛ مجموع فایل‌ها حداکثر **32 MiB** با تنظیم پیش‌فرض |
| قالب‌ها | `TXT` با UTF-8، `PDF` متنی، `DOCX` |
| PDF | تصویر اسکن‌شده یا رمزدار بدون متن قابل‌استخراج پذیرفته نمی‌شود؛ OCR وجود ندارد |
| اجرای مدل | حداکثر **۱ Inference هم‌زمان در هر Worker** و انتظار ورود به صف پیش‌فرض **۳۰ ثانیه** |
| HTTP health | فقط Liveness؛ به معنی آماده‌بودن مدل یا کیفیت خروجی نیست |
| ذخیره فایل | برنامه اسناد آپلودشده را به‌صورت دائمی ذخیره نمی‌کند؛ بافر/فایل موقت حین پردازش ممکن است استفاده شود |

| HTTP | معنی معمول |
| --- | --- |
| `200` | درخواست پردازش شده؛ در درخواست چندفایلی، `success` هر فایل را هم بررسی کنید |
| `400` | نام فایل یا Upload نامعتبر/خالی |
| `408` | توقف بیش‌ازحد جریان Upload |
| `413` | عبور از محدودیت حجم، تعداد یا بودجه پردازش |
| `415` | فرمت یا MIME پشتیبانی‌نشده |
| `422` | متن، مقدار `summary_length` یا محتوای فایل نامعتبر/غیرقابل استخراج |
| `500` | خطای داخلی در پردازش یا Inference |
| `503` | مدل در دسترس نیست یا سرویس تحت محدودیت منابع/صف است |

**مشکلات متداول:**

- **Swagger باز نمی‌شود:** اول `docker ps -a --filter name=mt5-persian-summary` را ببینید. اگر Container توقف کرده، `docker start mt5-persian-summary`؛ اگر هنگام شروع `health: starting` دیدید، Health را دوباره بررسی کنید. URL را در مرورگر باز کنید، نه به‌عنوان فرمان PowerShell.
- **`docker pull` خطای `denied` می‌دهد:** ابتدا موجودبودن Package و Tag در GHCR را بررسی کنید؛ برای Package خصوصی به احراز هویت با دسترسی `read:packages` نیاز است. هیچ Token را در کد یا لاگ قرار ندهید.
- **اولین خلاصه کند است یا `503` می‌دهد:** اتصال Hugging Face، فضای Cache، RAM و `docker logs --tail 100 mt5-persian-summary` را بررسی کنید؛ در صورت شکست بارگذاری اولیه، رفع عامل و Restart ممکن است لازم باشد.
- **خلاصه بسیار کوتاه، ناقص یا یکسان است:** از سلامت API نمی‌توان کیفیت مدل را نتیجه گرفت. روی نمونه‌های واقعی، پوشش موضوعات، جهت تغییرات، اعداد و نام‌ها را با متن مقایسه کنید. `long` تنها سقف توکن بالاتری تعیین می‌کند.
- **صفحه در سیستم دیگر باز نمی‌شود:** `localhost` به همان کامپیوتر اشاره دارد. این پروژه **Authentication یا Rate Limiting عمومی ندارد**؛ بدون درگاه امن و کنترل دسترسی نباید پورت را روی اینترنت باز کرد.

در تست قبلی کیفیت، مدل در یک نمونه چندموضوعی بعضی موضوعات را حذف کرد و جهت تغییر آلودگی را نادرست بازگو کرد. این مدل هنوز برای اسناد حساس، تصمیم‌های اداری مهم یا متون پزشکی/حقوقی بدون بازبینی انسانی مناسب نیست. **روی فایل محرمانه فقط با مجوز سازمانی تست کنید.**

## ۸. تست‌ها، ساختار پروژه و وضعیت تحویل

دستورهای توسعه‌دهندگان، پس از نصب `requirements.txt` و فعال‌کردن محیط مجازی:

```powershell
python -m pip check
python -m compileall -q src tests
python -m pytest -q
```

برای Smoke Test واقعی در برابر Container روشن (نیازمند Dependencyهای توسعه در محیط میزبان):

```powershell
python tests/e2e_http_smoke.py --base-url http://127.0.0.1:8002 --large-upload
```

**آخرین شواهد ثبت‌شده (2026-10-25):** در Windows تعداد **266 تست Passed و 2 هشدار Deprecation**؛ Image از GHCR دریافت شد، Container بیش از ۵۱ دقیقه در وضعیت `healthy` بود، `GET /api/v1/health` پاسخ `200` داد، و سناریوهای واقعی HTTP برای متن، TXT، PDF آزمایشی، DOCX، چندفایلی و خطاهای Upload موفق بودند. **این‌ها Benchmark کیفیت خلاصه، تست فشار یا تضمین امنیت Production نیستند.** تست واقعی Compose، Peak RAM و Graceful Shutdown زیر بار مستقل اجرا نشده‌اند.

ساختار اصلی:

```text
src/
  host/                    # FastAPI startup and YAML settings
  application/             # HTTP controllers, DTOs and upload validation
  core/services/           # Extraction, chunking and summarization logic
  infrastructure/          # Dependency injection and mT5 model provider
tests/                     # Unit, integration and opt-in live HTTP smoke
docs/                      # Architecture, model verification and progress
Dockerfile
compose.yaml
requirements.txt
```

برای جزئیات فنی و تاریخچه Acceptance: [`docs/IMPLEMENTATION_PROGRESS.md`](docs/IMPLEMENTATION_PROGRESS.md)، [`docs/STAGE2_MODEL_VERIFICATION.md`](docs/STAGE2_MODEL_VERIFICATION.md)، [`Service_Architecture_Guide_FA.md`](Service_Architecture_Guide_FA.md) و [`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md).

**وضعیت:** تمام ۸ مرحله MVP تکمیل شده‌اند؛ OCR، UI اختصاصی، Database، Authentication، Queue، Fine-tuning و تضمین وفاداری معنایی خلاصه‌ها **جزء این نسخه نیستند**.

**پایان کار با Docker (در صورت نیاز):**

```powershell
docker stop mt5-persian-summary
docker start mt5-persian-summary
```
