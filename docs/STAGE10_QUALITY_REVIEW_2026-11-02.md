# Stage 10 — Persian Summary Quality Evidence Audit (2026-11-02)

> **Decision: NO-GO.** Review of available Development evidence and the authorized sample source only. No new mT5 inference, independently adjudicated annotations or holdout access. This document does not replace an independent human review.

## Scope, sources, and provenance

- Code base: `Amirmahdimtz/mT5-Persian-Summary`, `main` before this document, commit `b82f3484ee73a79392896e87d1bd5896b2a24791`.
- Frozen CC0 synthetic Development fixture: `benchmarks/fixtures/quality_v1.json` (5 Development cases, 19 unique required facts; the 2 holdout cases were not evaluated).
- Previously recorded v4/v5 results: `docs/STAGE10_EXPERIMENT_V1.md` sections 20–25. The v5 raw run, draft labels and score were validated in a prior conversation, **but those underlying run/review JSON artifacts were not available for fresh re-adjudication in this assessment**. Counts below are carried forward from documented results, not new measurements.
- Previously recorded real-project-document v4 run: 2 Development Markdown documents (`real_architecture_guide` and `real_mvp_plan`), **medium only**; the `real_post_mvp_plan_holdout` remains sealed. The author of the provisional 5/6 labels was the assistant, not an independent reviewer.
- User-supplied original `persian_test.txt` and `persian_test.docx` were actually accessed and compared in this audit. The same authored content is also supplied as `persian_test.pdf`; existing user-side PDF extraction diagnostics were reviewed from chat logs, but the PDF bytes were **not** reprocessed as part of this source audit. The three formats count as **one source**.

## Development summary comparison — documented runs, not fresh inference

| Candidate | Tier | Covered / 19 required facts | Critical directional distortion | Short-vs-long distinction | Review status |
| --- | --- | --- | --- | --- | --- |
| v4 mT5-generated | medium | 3 covered; 2 distorted; 14 omitted | 2 observed inversions: pollution and software-support cost | 0/5 cases have distinct short and long outputs | Provisional assistant assessment |
| v5 source-sentence extractive | short | 4 covered, 15 omitted | 0 in assistant labels | 5/5 short differs from long | Provisional assistant labels |
| v5 source-sentence extractive | medium | 11 covered, 8 omitted | 0 in assistant labels | 5/5 short differs from long | Provisional assistant labels |
| v5 source-sentence extractive | long | 18 covered, 1 omitted | 0 in assistant labels | 5/5 short differs from long | Provisional assistant labels |

The v5 15-run record reports 49 assistant-segmented atomic claims with zero **assistant-labeled** unsupported claims, no token ceiling excess and no duplicate four-grams. Limits are 40/80/120 encoded tokens, with mean v5 usage 30.0/61.6/86.0 for short/medium/long. All 15 v5 results are **source-only selections without mT5 `generate`** and cannot demonstrate an improved generative mT5 model. `reviewed_runs=15` validates label completeness, not reviewer independence or entailment. The missing long fact is the disadvantaged-neighborhood clinic location. Medium still omits multiple important facts, despite reaching the frozen literal 8/19 gate. The weather source has identical v5 medium/long summaries, which does not by itself violate the frozen 3/5 short-vs-long gate.

The previous v4 authentic-project Development medium experiment had 5/6 assistant-labeled covered facts and 0 assistant-labeled critical fabrications, but only two independent project Markdown sources, no length comparison and no independent adjudication. It does not establish broad Persian document quality.

## New direct source inspection — the user's Persian test TXT and DOCX

Inspection performed directly on the original files in this assessment, independent of the historical benchmark summaries:

- UTF-8 TXT after `strip()`: **3,069 characters**, SHA-256 of its UTF-8 normalized bytes: `8caf50bb98c3a8c0c4051353318053db0a0964eebee94e4020072741371e15b2`.
- Nonempty-paragraph `python-docx` extraction: **3,055 characters**, SHA-256 of the joined UTF-8 paragraph bytes: `486806582036029938fc586f911d7173204e6693db6ad129a6f98c23cd19ff47`.
- After collapsing Unicode whitespace (`re.sub(r'\s+', ' ', text).strip()`), the TXT and DOCX strings are **identical**, both **3,055 characters**. This compares the original file contents, not model summaries.
- **12/12** deliberately selected, high-risk source anchors occur in both original TXT and DOCX strings, without modifying any source code. Exact literals appear below. This is a source-authoring/format parity check, **not summary fact coverage**.

| Review marker | Literal source evidence or source fragment | Safety obligation when reviewing summary |
| --- | --- | --- |
| hypothetical_scenario | `در یک سناریوی فرضی، سه منطقه شهری در یک دوره سی‌روزه بررسی شده‌اند.` | Do not present scenario observations as actual city data |
| fictional_disclaimer | `این داده‌ها صرفاً برای آزمایش نوشته شده‌اند و بیانگر وضعیت واقعی هیچ شهر یا نهادی نیستند.` | Retain fictional scope whenever any area finding is quoted |
| area1_increase | `منطقه نخست با افزایش درخواست‌های مرتبط با افت فشار مواجه است.` | Preserve area ID and increase direction, *and* fictional scope |
| area2_decrease | `در منطقه دوم، زمان رسیدگی به خرابی‌ها کاهش یافته` | Preserve area ID and decrease direction, *and* fictional scope |
| area3_increase | `در منطقه سوم، تعداد گزارش‌های تکراری بیشتر شده است.` | Preserve area ID and relative increase, *and* fictional scope |
| not_necessarily_network_fault | `افزایش مصرف الزاماً به معنای خرابی شبکه نیست` | Preserve `نیست`, not invert to a fault diagnosis |
| alternative_explanation | `شاید به تغییر فصل یا افزایش تعداد مشترکان مربوط باشد.` | Preserve uncertainty rather than assert a cause |
| quoted_leak_warning | `جمله «احتمال نشتی در مسیر شمالی وجود دارد» نباید به عبارت «نشتی در مسیر شمالی تأیید شد» تبدیل شود` | A prohibited quotation is not evidence that a leak was confirmed |
| conditional_frequency | `اگر در مجموعه‌ای از گزارش‌ها عبارت «کاهش فشار آب» بیش از سایر عبارت‌ها تکرار شود` | Maintain `اگر` conditional scope |
| frequency_not_importance | `تعداد تکرار به‌تنهایی میزان اهمیت موضوع را مشخص نمی‌کند.` | Preserve caveat against frequency-only importance |
| all_examples_fictional | `تمام مثال‌های آن فرضی هستند.` | Preserve disclaimer as applicable |
| Persian_digits | `۱۲۳۴۵` | Digit preservation is an extraction check, not a factual date/amount |

### Semantic failure modes identified by source and selector inspection

1. **Cross-sentence hypothetical scope:** the source contains a sentence introducing the fictional three-district scenario, then separate sentences reporting the area's increase/decrease. The experimental `_source_sentence_candidates()` separates those sentences, while `_source_sentence_final_async()` ranks and selects them independently. A selected sentence can therefore be literally extracted yet misleading if the `سناریوی فرضی` qualifier is absent. **Risk established; whether a particular actual run manifests it is not measured.**
2. **Quoted confirmation vs probability:** both `احتمال نشتی ...` and `نشتی ... تأیید شد` exist in the source as a cautionary *contrast*, not as confirmed events. Matching a quoted phrase lexically does not prove its factual entailment.
3. **Negative and uncertain claims:** `الزاماً ... نیست`, `شاید`, `اگر`, `نباید` and the global fictional disclaimer must be reviewed together with each selected claim; exact `phrase in source` is not a semantic metric.
4. **Different source containers vs independent documents:** TXT, DOCX and PDF here share authored content. PDF's known `کاملاً` → `کاملا&` difference is upstream of the project's RTL repair and present in both pypdf extraction modes; do not globally replace `&` or use literal anchor recall to estimate semantic accuracy.

## Stage 10 quality decision / frozen gates

| Gate | Evidence | Disposition |
| --- | --- | --- |
| Medium synthetic fact coverage at least 8/19 | v5 assistant-draft 11/19; v4 assistant estimate 3/19 | **Provisional only**, not independently signed off |
| 0 critical direction/date/person/number inversions; 0 distorted facts | v4 has 2 apparent direction inversions; v5 has 0 assistant-labeled distortions but contextual-scope risk | **Not independently verified** for v5; v4 NO-GO |
| Unsupported atomic claim rate at most 12.5% | v5 assistant-draft 0/49, no independent human claim adjudication | **Not independently verified** |
| Different short and long results for at least 3/5 development cases | v5 5/5; v4 0/5 | v5 **measured in prior run** (syntactic gate only) |
| Authentic diverse documents, reliable PDF/negation/conditional handling | 2 engineering Markdown sources + 1 multi-format synthetic user sample; no independent actual-field sample set | **Not satisfied** |
| CPU/RAM/inference cost and production compatibility | 402 passed full Windows tests at last code change; no new model run, peak RAM or independent performance benchmark | Engineering regression passed; semantic/perf signoff **not satisfied** |

**Final:** Stage 10 is **In Progress / Quality Blocked (Production NO-GO)**. The current default mT5 summarizer is not shown to meet the synthetic direction/coverage gates. v5 can remain a disabled-by-default extractive Development baseline only; neither the existing API defaults nor the frozen holdouts should change on this evidence.

## Reproducible next Development-only evaluation on distinct repository documents

The existing benchmark supports two distinct Development project documents. On the user's Windows clone after `git pull --ff-only origin main` and `$env:env_type = 'development'`:

```powershell
.\.venv\Scripts\python.exe -m benchmarks.project_document_dataset --output local_stage10_project_quality_v2.json
.\.venv\Scripts\python.exe -m benchmarks.quality_benchmark --dataset local_stage10_project_quality_v2.json run --split dev --lengths short medium long --output local_stage10_project_default_v2.json
.\.venv\Scripts\python.exe -m benchmarks.quality_benchmark --dataset local_stage10_project_quality_v2.json run --split dev --lengths short medium long --preserve-map-evidence --source-grounded-final --balanced-source-final --source-sentence-final --output local_stage10_project_extract_v5_v2.json
.\.venv\Scripts\python.exe -m benchmarks.quality_benchmark --dataset local_stage10_project_quality_v2.json review-template --runs local_stage10_project_default_v2.json --output local_stage10_project_default_review_v2.json
.\.venv\Scripts\python.exe -m benchmarks.quality_benchmark --dataset local_stage10_project_quality_v2.json review-template --runs local_stage10_project_extract_v5_v2.json --output local_stage10_project_extract_review_v2.json
```

The output review templates are **unreviewed**. Do **not** run `score` until an independent reviewer has labeled each fact and *all* atomic claims with exact source evidence. The dataset contains a holdout case in its manifest, but both `run` calls are strictly `--split dev`; this does not unseal the holdout. The local JSON files may contain sensitive source-derived summaries and must stay uncommitted.

To measure summarization quality on truly independent external Persian reports, at least two more separately authored, authorized documents and their actual generated `short`, `medium`, `long` outputs are still needed; the existing three containers of `persian_test` cannot substitute for that corpus. The current evaluation does not invent their results.
