
# Stage 10 — Project Development v2, Default mT5 vs v5 Extractive

Date: 2026-11-02. **Assistant-reviewed Development evidence only. Production NO-GO.**

## Data provenance and validation

- The user's fixed local dataset SHA-256 was fbc292ba36d07581614810efad42f0585ca9a50605e70a966048c33b9ac63e3c.
- Uploaded comparator and candidate run refer to six paired Development cases (two real project Markdown sources × short/medium/long). Six pairs succeeded; six had different output strings across methods.
- Canonical candidate run SHA-256 computed from uploaded JSON is ac4fa5ce8b182c0ee43a9e49fd2c667deb5868517908e70ec6e2826201b96a84; this equals the candidate_runs_sha256 recorded by the comparator.
- Baseline run hash e4846212186d4fea7afd21b39ffb851328350dd145688480bb56c7555b597b86 is in the comparator, but the original baseline run JSON was NOT uploaded. Consequently, no direct claim-level baseline review was performed.
- Original architecture and MVP plan uploads match the Git blob identities pinned in the dataset manifest, respectively 7fc7c6e8b3a0c9dbbcc57034dfc0c84135a440a8 and 2408d0488ebf01dd9fa2a7581192474685c2c833.
- The project holdout and both synthetic holdouts remain sealed. Project docs are not independent external Persian reports.

## Paired encoded token observations

| Development source | short default / v5 | medium default / v5 | long default / v5 |
| --- | ---: | ---: | ---: |
| real_architecture_guide | 24 / 33 | 24 / 74 | 24 / 118 |
| real_mvp_plan | 39 / 31 | 44 / 80 | 44 / 119 |

All six candidate outputs comply with tier ceilings (40, 80, 120 tokens); both candidate sources show distinct short/medium/long text. Baseline architecture has identical **token counts** across tiers, not necessarily identical raw text; the raw baseline file is unavailable for that claim. All six candidate four-gram repetition scores are zero. Candidate inference_mode is source_sentence_only_no_model_generate, so reported faster output duration is **not** a controlled mT5 generation speedup or equivalent workload comparison; peak memory and warm-up were not measured.

## Source fact coverage — assistant assessment, not independent human labels

Facts are the fixed reference facts in benchmarks/fixtures/real_project_documents_v1.json. After reviewing uploaded candidate summaries against the two original source documents:

| Source | Fact ID | short | medium | long |
| --- | --- | --- | --- | --- |
| architecture | mandatory_standard | omitted | omitted | covered |
| architecture | no_unnecessary_interface | omitted | omitted | omitted |
| architecture | constructor_injection | omitted | omitted | omitted |
| MVP plan | file_formats | omitted | omitted | omitted |
| MVP plan | multi_file | covered | covered | covered |
| MVP plan | eight_stages | omitted | omitted | omitted |

Observed v5 coverage: **short 1/6**, **medium 1/6**, **long 2/6**. These are provisional assistant interpretations and have NOT been adjudicated by an independent reviewer or scored through a completed human review. The medium observation is **below the previously frozen authentic Development threshold of 3/6**.

### Confirmed structural defect in the uploaded pre-fix candidate

MVP plan medium and long both end with the incoherent fragment **کارها:** 1. The original text contains a bold Markdown section label followed by a numbered instruction list. The existing source-sentence selector recognized unnumbered list items but joined the label with a long numbered line and split after its 1. marker, treating the label plus number as a complete Persian sentence. This fragment is not an atomic factual claim and should not be counted as meaningful coverage.

This update adds a minimal guard *only* to the opt-in v5 source-sentence candidate extractor: recognize numbered Markdown list lines as a boundary and discard the list marker before selecting the actual sentence. Existing numbered PDF section-heading detection is kept ahead of the list matcher; a new fake-provider regression checks that the isolated label and number never appear as a summary sentence. **The uploaded comparison is based on pre-fix code.** The fix is not a semantic solution for missing required source facts or cross-sentence negation/scope.

## Verification and decision

- No new complete pytest or actual mT5 inference was performed by the assistant. Previous user's Windows full-suite result: 402 passed, zero failed, two warnings on an older code head. New focused/full Windows tests are still required.
- No unsupported-claim rate, independent semantic fact coverage, number/date/negation preservation, or Stage 10 production GO was certified by this limited Development review.
- Source-only candidate cannot be claimed as an improved abstractive mT5 model.
- Next: test the focused patch and full suite; rerun only candidate v5 Development to a *new* filename; compare with the unchanged baseline dataset/run; perform independent claim and fact adjudication (six facts per tier per method) before scoring. Evaluate independently authored Persian TXT/PDF/DOCX reports before promotion.

## Windows post-fix confirmation — v5 v3 (2026-11-03)

- Commit tested by the user on Windows: **184b6ac44346bf08e073e4a27f704bd24c38e759**. Fast-forward pull and HEAD verified in terminal log.
- Environment checks: pip check **no broken requirements**; compileall -q src benchmarks tests completed without error. Focused pytest: **60 passed in 4.73 seconds**; full pytest: **403 passed, 0 failed, 2 existing deprecation warnings in 12.64 seconds**. These are **user-run tests**, not assistant/container execution. Two warnings are Starlette TestClient/httpx deprecation and httpx content upload deprecation.
- User ran the unchanged pinned Development project dataset, --split dev --lengths short medium long with all v5 opt-in flags. File: local_stage10_project_extract_v5_v3.json, generated at 2026-11-03T06:34:56.036640+00:00; Windows Python 3.12.10, CPU. Source-only inference_mode: source_sentence_only_no_model_generate; there was no mT5 generate call in this candidate path. The run file was uploaded and inspected.
- Verified local dataset SHA-256 still **fbc292ba36d07581614810efad42f0585ca9a50605e70a966048c33b9ac63e3c**. v3 canonical JSON runs_hash is **f4f3795213bfcb45cfc3da40fcaebc61aedfb614d0375f32395a9c03084e8537**. The prior v2 uploaded candidate runs_hash is **ac4fa5ce8b182c0ee43a9e49fd2c667deb5868517908e70ec6e2826201b96a84**.
- The user ran the existing baseline-v2 vs candidate-v3 comparison and the CLI reported **paired=6, changed=6, semantic quality NOT REVIEWED**. Its new comparison JSON is not uploaded; a new comparison report's hashed metadata was **not** independently verified.

| Source / tier | v5 v2 tokens | v5 v3 tokens | Exact summary text changed? |
| --- | ---: | ---: | --- |
| Architecture short | 33 | 33 | No |
| Architecture medium | 74 | 74 | No |
| Architecture long | 118 | 118 | No |
| MVP short | 31 | 31 | No |
| MVP medium | 80 | **74** | Yes, removed orphan list prefix |
| MVP long | 119 | **113** | Yes, removed orphan list prefix |

- Exact diff of the two uploaded raw v5 runs shows **only** the sentence **کارها:** 1. was removed from MVP medium and long; other selected sentences did not change. All six results have no error_code, and all stay within fixed encoded-token ceilings 40/80/120. Both documents still have distinct short, medium and long outputs.
- **Provisional reference fact coverage remains short 1/6, medium 1/6, long 2/6** (assistant source-based labels). Medium is **still below** the frozen real-project Development gate >=3/6. The revised MVP long result still emits the semicolon-terminated excerpt 'کد هر مرحله کامل باشد؛' without its following qualification about placeholders; architecture medium similarly selects a semicolon-ended clause while excluding its continuation. This is a residual source-context/completeness concern, not proof of a new fabricated fact.
- **Conclusion:** the specific numbered-list regression is fixed and verified on Windows; the original Stage 10 quality problem is **not** solved. Do not enable the opt-in v5 mode in Production, do not loosen acceptance gates or access holdouts. Avoid further punctuation heuristics without representative semantic review; first audit actual missing facts and cross-sentence scope, inspect the as-yet-unprovided raw default-v2 run for fair factual comparison, and obtain human claim-level assessment and distinct Persian field documents.

## Full paired raw-output semantic audit — default mT5 v2 versus v5 v3 (2026-11-03)

### Input provenance and integrity

The user supplied the previously missing authentic-project Development **baseline run** `local_stage10_project_default_v2.json` and the **v3 comparator** `local_stage10_project_compare_default_v5_v3.json`. The earlier uploaded `local_stage10_project_extract_v5_v3.json` was also directly re-opened for this audit. All artifacts were inspected as JSON; the comparator and both full raw runs agree on fixed dataset SHA-256 `fbc292ba36d07581614810efad42f0585ca9a50605e70a966048c33b9ac63e3c`, split `dev`, and exactly 6 successful paired source/tier results (2 distinct project Markdown sources × 3 tiers). Canonical hash verification (`json.dumps(sort_keys=True,ensure_ascii=False,separators=(",",":"))` with UTF-8 SHA-256):

- Original default mT5 v2: `e4846212186d4fea7afd21b39ffb851328350dd145688480bb56c7555b597b86`, matches `baseline_runs_sha256`; `inference_mode=mt5_generate`.
- Opt-in v5 v3: `f4f3795213bfcb45cfc3da40fcaebc61aedfb614d0375f32395a9c03084e8537`, matches `candidate_runs_sha256`; `inference_mode=source_sentence_only_no_model_generate`.
- All 6 baseline/candidate pairs contain nonempty text and no `error_code`; all 6 pairwise strings are different. The two methods use the same pinned model metadata, but **only the baseline invokes mT5 generation**. The v5 source-only text is not an improved mT5 decoder.
- No holdout was accessed; the original two development Markdown documents and fixed reference fact definitions were used for source inspection. The report reflects an **assistant-authored semantic assessment**, not an independently adjudicated human quality score.

### Actual output and tier distinctions

| Source | Default short / medium / long encoded tokens | v5 short / medium / long encoded tokens | Default distinct tier strings | v5 distinct tier strings |
| --- | --- | --- | ---: | ---: |
| `real_architecture_guide` | 24 / 24 / 24 | 33 / 74 / 118 | **1 of 3** | **3 of 3** |
| `real_mvp_plan` | 39 / 44 / 44 | 31 / 74 / 113 | **2 of 3** | **3 of 3** |

All 12 outputs respect the respective fixed length ceilings `short=40`, `medium=80`, `long=120` encoded tokens. Both v5 sources have different `short` and `long` summaries; only the MVP source does so for default mT5. This is a two-source observation, not the frozen five-case synthetic tier gate. No baseline or v5 output here repeated Unicode four-grams according to the uploaded comparator.

**Verbatim baseline snippets (now available):**

- Architecture, all three tiers: `برای انتقال استاندارد معماری به چتGPT یا هر توسعه دهنده کافی است.` The claim paraphrases the original document's self-described purpose, but omits every one of its three frozen substantive facts: binding standard, prohibition on unnecessary interfaces, and `@inject` constructor DI.
- MVP, short: `برای پیاده سازی سرویس خلاصه سازی اسناد فارسی با MT۵ طراحی شد. برای اجرای سورس Repository پروژه قواعد اجرا را` — the second sentence is syntactically **unfinished**.
- MVP, medium and long (identical): `برای پیاده سازی سرویس خلاصه سازی اسناد فارسی با MT۵ طراحی شد. برای اجرای سورس Repository پروژه قواعد اجرا را بررسی می کند.` The source supports a staged implementation plan but does **not** state this particular agent/action in this phrasing. The second sentence is semantically awkward and a **potential unsupported or distorted paraphrase**, not a proven hallucination-rate number without reviewer adjudication.

**v5 remaining context risk:** the targeted v3 patch removed the malformed `**کارها:** 1.` phrase; the v3 MVP long excerpt still ends with `کد هر مرحله کامل باشد؛` while the original source continues with a condition rejecting hypothetical files, placeholders, TODO and pseudo-code. The architecture medium excerpt `در خروجی کدنویسی، فایل‌ها را کامل و قابل‌اجرا تولید کن؛` likewise stops before the original's follow-up. These are *source-derived but incomplete* fragments, illustrating that extractive lexical matching does not prove stand-alone semantic sufficiency.

### Frozen Development fact audit (assistant-only labels)

The exact six source facts are from `benchmarks/fixtures/real_project_documents_v1.json`. Each source/tier has the same three expected facts; values below represent **assistant-reviewed** meaning, not human-independent scoring.

| Source / fixed fact | Default short | Default medium | Default long | v5 short | v5 medium | v5 long |
| --- | --- | --- | --- | --- | --- | --- |
| Architecture: `mandatory_standard` | omitted | omitted | omitted | omitted | omitted | **covered** |
| Architecture: `no_unnecessary_interface` | omitted | omitted | omitted | omitted | omitted | omitted |
| Architecture: `constructor_injection` | omitted | omitted | omitted | omitted | omitted | omitted |
| MVP: `file_formats` (TXT/PDF/DOCX) | omitted | omitted | omitted | omitted | omitted | omitted |
| MVP: `multi_file` | omitted | omitted | omitted | **covered** | **covered** | **covered** |
| MVP: `eight_stages` | omitted | omitted | omitted | omitted | omitted | omitted |
| **Total / 6** | **0/6** | **0/6** | **0/6** | **1/6** | **1/6** | **2/6** |

For **medium**, baseline 0/6 and v5 1/6 both fail the frozen authentic Development gate `>=3/6`. These totals reflect only six unique frozen source facts repeated at three output lengths; the 18 assessments per method are **not independent source facts**. No separate independent claim segmentation, direct textual-entailment verification, numerical/date/polarity adjudication or `score` command was performed. Unsupported-claim rates for both candidates remain **NOT_SCORED**, rather than a misleading zero. The experimental v5 does not demonstrate reliable negation, hypothetical, conditional or quotation scope on distinct external reports.

### Decision, reproducibility and next action

**Stage 10 remains In Progress / Quality Blocked (Production NO-GO).** The complete baseline confirms poor coverage and poor length differentiation in default mT5, and v5 offers a controlled extractive alternative with better literal selection but still fails the real-project medium fact gate. The observed mT5 generation durations around 60–85 seconds per output versus warm v5 milliseconds are not comparable model-speed measurements: one performs generation and the other does not; cold-start/peak RAM are unstandardized.

No source/config/benchmark fixture/holdout/API/default flags were changed for this review. User's latest proven Windows verification for the v3 source patch: focused **60 passed**, full **403 passed / 2 warnings**, `pip check` and `compileall` successful. Those tests predate this documentation-only update; tests were **not rerun** for this report.

Use the **existing** Stage 9 `quality_benchmark review-template` mechanism against the unchanged baseline-v2 and v5-v3 raw files, but only complete factual and claim annotations after independent source examination. Do not copy assistant labels into a file named "independently verified". Keep private/local output JSON files outside Git history. Prioritize a *general* information-coverage and cross-sentence-context design on varied authorized Persian documents rather than tuning to two Markdown guides; preserve holdout isolation and frozen gates.

## Assistant-prepared source-evidence review template completed (2026-11-03)

- **Input:** User uploaded `local_stage10_project_extract_review_v3.json` containing 6 records, each with 3 null fact labels and no claims. Its `runs_sha256=f4f3795213bfcb45cfc3da40fcaebc61aedfb614d0375f32395a9c03084e8537` matches the already supplied `local_stage10_project_extract_v5_v3.json`, which has dataset SHA `fbc292ba36d07581614810efad42f0585ca9a50605e70a966048c33b9ac63e3c`; split is Development only.
- **Deliverables to user (local, not committed):** `local_stage10_project_extract_review_v3_assistant_draft.json` and `STAGE10_V5_V3_ASSISTANT_REVIEW_NOTES.md`. Each original output sentence and every selected exact `evidence_quote` were verified as substrings of the corresponding original authorized Markdown source. The review-draft `instructions` clearly state `ASSISTANT-PREPARED DRAFT ONLY; NOT INDEPENDENT HUMAN REVIEW`. No existing user-run files were overwritten or modified.
- **Assistant-proposed facts:** 18 labels on 6 source/tier results (the same six unique facts repeated across three tiers): **covered 4 / omitted 14 / distorted 0**; `short 1/6`, `medium 1/6`, `long 2/6`. Medium still **fails** the frozen authentic Development threshold `>=3/6`.
- **Assistant-proposed atomic claims:** **22** claim objects, all labeled `supported=True` with exact source evidence quotes. These are *provisional assistant labels* only; **0/22 is not a human-verified unsupported claim rate**. Source evidence presence checks do not establish full semantic entailment or coverage. The source-extractive architecture and MVP excerpts ending with semicolons omit same-line qualifiers about placeholders/TODO and pseudo-code; a second reviewer must consider contextual distortion/incompleteness.
- **Verification:** The generated JSON is syntactically valid; six source/tier keys and expected fact IDs match, its `runs_sha256` equals the actual v3 run canonical hash, and all 22 cited source excerpts exist in the original texts. `quality_benchmark score` was **not run** because the separate fixed local prepared dataset is not uploaded, and no independent human review has occurred. No model inference, pytest, external-field document testing, or holdout access in this audit.
- **Decision:** Stage 10 **In Progress / Quality Blocked (Production NO-GO)**. Do not relabel an assistant draft as independently verified, do not enable v5 in the API, and do not claim source-only extraction improves mT5 generation. Obtain independent fact and claim review on Development and representative authorized Persian documents before further pipeline changes.

## Development-only v6 selector trial: salience and semicolon scope (2026-11-03)

The user's next request authorized a targeted continuation of Stage 10 information-coverage work, **not** production promotion. The source-only v5 baseline had a confirmed medium factual-coverage failure (1/6 on two Development project Markdown documents) and selected semicolon-ended fragments that omitted subsequent conditions. Source review showed the selector's boolean `_SOURCE_SIGNAL` (3 points for broad words including "program"/"execution") and unseen-paragraph reward (3 points) displaced substantive statements about capabilities, prohibitions, and explicit requirements.

**v6 opt-in changes:** A source-specific terminal sentence split preserves inline semicolon qualifiers; one-blank PDF layout rejoining no longer treats `؛` as a final terminator. Generic—not fixture-ID-specific—source signals are reweighted: capability/negative imperative 4, explicit obligation/numeric quantity 3, technology and code markers 1, broad action words 1. An unseen-paragraph bonus of 1, lead boost of at most 3 within the first 24 candidates, and a shorter-token tie-break are applied without changing the fixed count/tokens/character budgets or preserved document order. Candidate extraction keeps Markdown heading exclusions and fenced-code skipping. A phrase such as `نمی‌تواند` is not counted as affirmative capability. The user-facing API and normal mT5 generation path remain unchanged.

**New tests:** Generic fake-provider regressions for preserving semicolon-attached negation/explanation; retaining a complete `TODO` constraint after a semicolon; preference for actionable facts over generic introduction under short budget; and not treating `نمی‌تواند` as affirmative capability. Existing tests still cover PDF line rejoining, scope exclusions, raw-work limits, source-only inference, invalid flags and frozen Development/holdout isolation.

**Evidence status:** Isolated local regex/selection preflight was run successfully with the two original authorized source documents. **Full integrated tests and real mT5 tokenizer validation are not run here** and no new fact-covering benchmark result is claimed. The pre-v6 uploaded mT5/v5 JSON artifacts and review annotations remain the historical baseline. The expected effect on the frozen 6 Development facts, 19 synthetic Development facts and diverse Persian text is unknown until the user's Windows rerun. If token ceilings or contextual safety regress, revert this opt-in trial. **Production NO-GO; all holdouts remain sealed.**

## v6 Windows regression and targeted root-cause fix (2026-11-03)

The user's Windows tests on commit `7df33d326a3cf128b368c0670a34e3e16040895b` exposed a **real regression** after the v6 salience reweighting: focused tests **63 passed, 1 failed**; full tests **406 passed, 1 failed, 2 warnings**. Both failures were the same original direction/number preservation unit test. The `medium` fake-provider summary omitted the reduction in network maintenance cost (80→65), retaining only the increase in software support cost (30→36) and contract review.

**Root cause:** The v6 `_SOURCE_CAPABILITY` regex gave +4 generic service-capability points to *any* text mentioning the noun `پشتیبانی`. The two support-cost/contract sentences were incorrectly classified as service capabilities, displacing the first numeric direction claim under the 32-token fake-tokenizer budget. A prior semantic-coverage change therefore broke a safety regression, even though its CLI benchmarking completed successfully; this is not merely a stale test.

**Scoped fix:** Within the optional source-sentence selector, only positive verbal patterns like `پشتیبانی می‌کند` or `پشتیبانی می‌شود` receive that capability weight; nominal support costs and service contracts no longer do. Existing negative `نمی‌تواند` recognition remains excluded. A new unit test checks nominal expense/contract versus actual service capability without altering any pre-existing assertion. Original direction/number test is intentionally preserved.

An offline preflight using the exact failing Persian fixture and fake-token counter ranked network cost reduction and software support cost increase equally (4 points each), ahead of contract review (1 point), and selected both statements (27 tokens under a 32-token medium ceiling); this is **not a repository pytest pass**. The revised code still requires focused/full tests and real tokenizer benchmarking on the user's Windows environment. Earlier `local_stage10_project_extract_v6_v1.json` outputs predate this fix; preserve them, compare against a fresh v6 candidate after testing. No frozen benchmark labels, Production model/API settings, or holdout content changed. **Stage 10 Production NO-GO**.

### Immediate regex-escape correction after nominal capability fix

Post-commit review found the first nominal-cost patch accidentally committed an escaped regex sequence `\\\\s+` inside a Python raw regex; this matches a literal backslash and would break the new positive verbal-support test. The follow-up fix uses the correct single-backslash `\\s+` whitespace token. A Python regex sanity check confirms affirmative `پشتیبانی می‌کند` and `پشتیبانی می‌شود` match and nominal `هزینه پشتیبانی` and `قرارداد پشتیبانی` do not. User must run the real focused/full Windows pytest on the **newest** Git SHA. No test success or production readiness is claimed for this code-only adjustment.

## v6 v2 Windows verification and comparator-only evidence (2026-11-03)

The user's Windows clone at code SHA `1132955c7c6789e9e17e916a1ec4e0eccc2ef520` passed the **21 focused v5/v6 tests (1.40s)** and the **complete 408-test regression suite (12.98s)**, with 0 failures and 2 previously observed third-party deprecation warnings. This is the first user-confirmed green regression suite following the v6 nominal-support capability patch; the old cost-decrease preservation assertion was not weakened. These tests were performed on the user's system, not in the assistant environment.

The user verified the unchanged pinned Development dataset hash `fbc292ba36d07581614810efad42f0585ca9a50605e70a966048c33b9ac63e3c` and completed a six-output opt-in v6 v2 run. The **comparison JSON was uploaded and inspected**, but the **actual raw v6 v2 run JSON has not been uploaded**.

### Observations from comparator versus original baseline and historical v5 v3

| Source | Tier | Default mT5 tokens | v5 v3 tokens | v6 v2 tokens | Budget |
| --- | --- | ---: | ---: | ---: | ---: |
| `real_architecture_guide` | short | 24 | 33 | **13** | 40 |
| `real_architecture_guide` | medium | 24 | 74 | **69** | 80 |
| `real_architecture_guide` | long | 24 | 118 | **114** | 120 |
| `real_mvp_plan` | short | 39 | 31 | **31** | 40 |
| `real_mvp_plan` | medium | 44 | 74 | **74** | 80 |
| `real_mvp_plan` | long | 44 | 113 | **120** | 120 |

All 6 baseline-v6 pairs are reported successful and text-different. All candidate values respect the encoded-token limits. Comparator records `baseline_runs_sha256=e4846212186d4fea7afd21b39ffb851328350dd145688480bb56c7555b597b86`, `candidate_runs_sha256=5a9ed374ca43cabf2119f4b2b45d604953225cc1f275185eccef5cc0a9f1a2bc`, and `semantic_review_status=NOT_REVIEWED`. It also reports zero repeated 4-grams. These metadata are from an actual user-provided JSON artifact; the candidate run file itself is absent, hence its hash and text cannot be independently verified by reading the candidate bytes.

**Interpretation limits:** v6 architecture short fell from 33 to 13 tokens versus v5 v3, and MVP long now uses the full 120-token ceiling. Neither change proves improved fact coverage or polarity/number/date safety. The six-pair comparator compares *default mT5 to v6*, not *v5 v3 to v6*; values at the same token counts do not imply equal strings. v6 remains source-only (`source_sentence_final` flag) and is not a better mT5 generator. Cold-start times, independent human claims, the frozen medium >=3/6 fact gate, and the cross-document semantic gate remain unverified.

**Decision: Stage 10 In Progress / Production NO-GO.** Do not further tune the selector until the raw v6 v2 result is inspected against the original two Development source documents and v5 v3, and independently reviewed. No Production settings or holdouts changed as a consequence of these green engineering tests.

## v6 v2 actual raw-output assessment (2026-11-03)

The previously missing `local_stage10_project_extract_v6_v2.json` has now been supplied and inspected. Its canonical sorted UTF-8 JSON hash `5a9ed374ca43cabf2119f4b2b45d604953225cc1f275185eccef5cc0a9f1a2bc` **exactly matches** `candidate_runs_sha256` in the uploaded `local_stage10_project_compare_default_v6_v2.json`. The baseline hash remains `e4846212186d4fea7afd21b39ffb851328350dd145688480bb56c7555b597b86`, and all artifacts use the fixed Development dataset SHA-256 `fbc292ba36d07581614810efad42f0585ca9a50605e70a966048c33b9ac63e3c`.

Actual text has now been compared against the uploaded v5 v3 source-extractive run and both original authentic engineering Markdown sources. All **16** output lines across the six v6 v2 responses occur **verbatim** in their corresponding source documents; there are no CLI failure records, and the 40/80/120 encoded-token ceilings are satisfied. This only validates textual provenance, not independent meaning/scope, entailment or unsupported-claim rate. No holdout text was used.

| Source | Tier | v5 v3 tokens | v6 v2 tokens | Key v6 meaning |
| --- | --- | ---: | ---: | --- |
| Architecture | short | 33 | **13** | Explicitly prohibits unnecessary service/repository interfaces |
| Architecture | medium | 74 | **69** | Prohibits unwarranted architecture transformations and unnecessary interfaces |
| Architecture | long | 118 | **114** | Adds mandatory-standard status; contains incidental conditional Alembic/DB guidance |
| MVP plan | short | 31 | **31** | Multi-file handling; exact same text as v5 |
| MVP plan | medium | 74 | **74** | Multi-file handling and roadmap context; exact same text as v5 |
| MVP plan | long | 113 | **120** | Adds direct-text and TXT/PDF/DOCX support, preserves multi-file; uses full token budget |

### Source-by-source frozen fact labels (assistant-only, not independently approved)

| Source / fact ID | v5 short | v5 medium | v5 long | v6 short | v6 medium | v6 long |
| --- | --- | --- | --- | --- | --- | --- |
| Architecture: `mandatory_standard` | omitted | omitted | covered | omitted | omitted | covered |
| Architecture: `no_unnecessary_interface` | omitted | omitted | omitted | **covered** | **covered** | **covered** |
| Architecture: `constructor_injection` | omitted | omitted | omitted | omitted | omitted | omitted |
| MVP plan: `file_formats` | omitted | omitted | omitted | omitted | omitted | **covered** |
| MVP plan: `multi_file` | covered | covered | covered | covered | covered | covered |
| MVP plan: `eight_stages` | omitted | omitted | omitted | omitted | omitted | omitted |
| **Total / six source facts** | **1/6** | **1/6** | **2/6** | **2/6** | **2/6** | **4/6** |

This is **a measurable improvement in provisional coverage**, not a frozen-gate pass: v6 `medium=2/6` is **below >=3/6** required by the real-project Development acceptance criterion. Architecture medium and long favor multiple prohibitions over constructor DI; MVP long allocates scarce 120 tokens to a generic target-tree sentence while omitting eight-stage structure. v6 short is concise but focuses on one architecture rule rather than a representative introduction. A source-extractive approach may still omit nearby qualifiers or imply misleading context when sentences are separated from sections; the source's conditional Alembic rule should not be interpreted as requiring a database for the current MVP. `inference_mode=source_sentence_only_no_model_generate` means **this did not improve the mT5 generation model**.

**Verification and decision:** The last user-run Windows code validation at `1132955c7c6789e9e17e916a1ec4e0eccc2ef520` was 21 focused tests passed, full suite 408 passed / 2 third-party deprecation warnings. No new tests or model inference were done for this report. `semantic_review_status=NOT_REVIEWED` and unsupported-claim rate **NOT_SCORED**; no independent semantic judgments or peak-RAM evidence. No Production GO, model/config/API change, new fixture tuning or holdout use. Further refinement should be assessed on authorized diverse Persian sources and independently verified claims rather than tuning against the two Engineering Markdown documents.
