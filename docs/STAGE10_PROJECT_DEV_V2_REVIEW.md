
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
