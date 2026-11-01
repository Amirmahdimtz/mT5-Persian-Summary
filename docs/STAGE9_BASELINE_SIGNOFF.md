# Stage 9 — Reproducible Diagnostic Baseline and Engineering Handoff

> **As-of:** 2026-11-01
> **Project:** `mT5-Persian-Summary`
> **Scope:** Stage 9 engineering/diagnostic baseline only; **not a claim of production-grade model accuracy**
> **Status:** Engineering acceptance checklist satisfied on the available, fixed **development** data. Independent human adjudication and representative external-document evaluation are outstanding **release / Stage 13 evidence gates**, not fabricated successes.
> **Model:** `nafisehNik/mt5-persian-summary`, revision `b575560ad967050e77a40f907abb1ebbeefb9a15` (CPU)

## 1. Exact provenance and limits

The user ran `quality_benchmark` with Python 3.12.10 on Windows 11 using the pinned CPU model. The two published dataset inputs are:

| Dataset | Version/provenance | SHA-256 of user's materialized JSON | Development outputs seen | Reserved holdout |
| --- | --- | --- | --- | --- |
| `benchmarks/fixtures/quality_v1.json` | 7 original CC0 synthetic Persian scenarios | `cc907d6b16a4b68685b280002bb0a0f550ce6ce3966941c8732702c016f8a9a9` | 5 sources × 3 tiers = 15 model calls | 2 synthetic cases, **not run** |
| `benchmarks/fixtures/real_project_documents_v1.json` | References 3 existing GitHub Markdown documents; `PROJECT-REFERENCE-ONLY` | `fbc292ba36d07581614810efad42f0585ca9a50605e70a966048c33b9ac63e3c` | 2 sources × medium = 2 model calls | 1 real document, **not run** |

**17 actual model calls** across **7 distinct development sources**. Do **not** treat the 15 tier responses as 15 independent documents. The authentic repository documents are Markdown, not third-party PDF or DOCX files. Raw local run/review JSONs are intentionally not committed. These observations have not been reproduced in the assistant sandbox with real weights; inference success is supported by the user's logged output.

## 2. Baseline findings, with measured and unmeasured fields

### Synthetic dev: five unique documents

- Assistant-drafted fact annotations subsequently passed the user's `score` workflow: **3/19 covered = 15.79%**, **14/19 omitted = 73.68%**, **2/19 distorted = 10.53%**. Those two distortions are the **pollution decrease → increase** and the **software support expense 30→36 increase → decrease** inversions.
- **Unsupported atomic claims: 3/8 = 37.5%**, with a disputable interpretation of the weather announcement as a `warning`; excluding that one yields **2/8 = 25%**. Both are preliminary and depend on a consistent claim-segmentation policy.
- **5/5 synthetic sources** produced byte-identical `short`, `medium`, `long` outputs, with output token counts **19–33 including specials** and mean **66.2 characters** per tier. A generation token ceiling is **not** a minimum summary length.
- Three required failure scenarios reproduced on real pinned mT5: **short news** omitted advice; **multitopic** omitted sections and inverted direction; **long repeated text** lost teacher training, school infrastructure, phased rollout and underserved-school priority. The long case deliberately repeats one paragraph 18 times; it does not establish the behavior on a varied multi-section document.
- Four-word lexical repetition fraction across the five distinct medium outputs is **0%**; the failure on these cases is chiefly omission and semantic distortion, not n-gram looping.

### Two authentic repository-document dev outputs (medium only)

- `real_architecture_guide`: 46 encoded tokens, 75.247s reported; output repeatedly says the guide is for ChatGPT and omits `@inject`, mandatory architectural standard, and avoiding unnecessary interfaces.
- `real_mvp_plan`: 23 encoded tokens, 50.958s reported; output mentions a Persian mT5 summarization service without retaining the TXT/PDF/DOCX formats, multiple-file support or eight stages.
- The user-scored review reports **0/6 covered; 6/6 omitted; 0/6 distorted**, and **0/2 unsupported** broad output claims. **Zero unsupported claims is not success** when zero required facts survive.
- On these outputs, the four-word duplicate-window fraction is **40% for the architecture case**, **0% for the plan**, **20% across the two**; **1/2** outputs contains repeated four-grams.
- Mean encoded output length including specials is **34.5 tokens**, below the **80-token medium ceiling** for both; mean characters **91.5**. `short/long` have **not** been run for these real documents. Total measured wall time for these two calls is **126.205s**, not a warm-only inference latency comparison.

### Verification facts and caveats

- The user's **last full regression run** before the new repetition/length instrumentation: **300 passed, 2 nonblocking deprecation warnings** on Windows. Targeted Stage 9 at that point: **34 passed**.
- After adding deterministic repetition/token-ceiling instrumentation: **37 Stage 9 tests passed** and `compileall` passed in an isolated assistant Python environment; user-side Windows and whole-suite rerun **not yet observed**.
- Peak RSS/RAM, standardized warmed latency, 8-page source PDF extraction, third-party meeting minutes, independent human reviewer agreement, and raw map-stage vs reduce-stage summaries are **not measured**. The sample-size target of 30–50 legally usable representative documents and 100 labelled questions is deferred to the Stage 13 acceptance set, not falsely declared complete.

## 3. Extraction versus model failure: evidence-based causal triage

| Observation | Established conclusion | What remains unproven | Stage 10/11 action |
| --- | --- | --- | --- |
| Wrong pollution and expense directions on original synthetic plain text | These inversions **cannot originate in PDF/DOCX extraction** because no file extraction occurred. | Whether errors originate in checkpoint decoding, hierarchy, or earlier chunk transformations. | Trace direct single-chunk generation and final-pass summaries using the same checkpoint before changing parameters. |
| Same output at all three length ceilings | Requested length levels do not meaningfully differentiate the observed texts. | The cause; `max_length` is an upper bound and the model may stop early. | Compare fixed-input generation and EOS timing across budgets; do not assume a larger `max_length` suffices. |
| ChatGPT phrase loop in architecture-guide Markdown | A **40% repeated-four-gram** result is measured on generated text. | Whether loop first appears in map outputs, reduction inputs, or the final generate call. | Instrument the map/reduce boundary and compare repetition penalties on fixed text with unchanged weight revision. |
| Missing six task-specific facts in two Markdown documents | Document coverage is demonstrably poor; file parsing is not the explanation because raw Markdown text was passed to the summarization service. | Exact hierarchy stage where information disappeared. | Source-to-chunk coverage and map/reduce fact audit; preserve section boundaries and explicit fact checks. |
| Anecdotal prior 8-page PDF produced identical medium/long summary | Prior user observation only; useful regression candidate. | PDF text order, RTL layout, page/anchor extraction accuracy because original PDF bytes are unavailable. | Use `inspect-extraction` with exact source anchors on a permitted **selectable-text PDF** before blaming mT5. |

**Prioritization:** (1) correctness of direction/date/person/number, (2) coverage in map/reduce, (3) output repetition, (4) length differentiation, (5) measured throughput and memory. These are *diagnostic priorities*, not asserted root-cause locations.

## 4. Frozen **Stage 10 development regression** gates (protocol v1)

Freeze these thresholds **before** any Stage 10 tuning. They are **development stop/go gates on these small fixed samples**, not production quality guarantees.

| Metric | Baseline | Stage 10 gate |
| --- | --- | --- |
| Unique synthetic dev fact coverage (`medium`, 19 facts) | 3/19 | **At least 8/19** covered (42.11%) |
| The two critical direction inversions | 2 | **0**, and no new date/number/person inversions |
| Synthetic dev fact distortion (`medium`) | 2/19 | **0/19** |
| Synthetic dev unsupported claim rate | 3/8 (weather label disputed) | **≤12.5%** with reviewer-agreed atomic-claim segmentation |
| Synthetic dev length tiers | 5/5 identical | **≥3/5** distinct short versus long outputs; no repetition-fuelled expansion |
| Real project-document required facts (`medium`, 6 facts) | 0/6 | **≥3/6** covered with **zero critical fabricated facts** |
| Real project architecture four-gram repetition | 40% | **0%** duplicate four-grams on that specific regression case |
| API compatibility | User's prior 300 passing | No new failures in full test suite |

**Scoring policy:** count unique source facts once per tier, preserve all original source quotes, review unsupported claims atomically, record all comparisons with immutable dataset hashes and unchanged test split. Any ambiguous fact must be explicitly adjudicated, not silently reclassified. A candidate failing a critical direction/number/date correctness condition is **NO-GO**, even if coverage improves. Keep all holdout cases untouched until development candidates and gates are locked.

## 5. Forward gates for Stages 11 and 13

These are **precommitted candidate thresholds**, subject to approval against a representative *future* question/document set; they are not measurements:

- **Stage 11 retrieval:** Evidence `Recall@3 ≥ 90%` for questions with an answer; *all* returned source locations must be checkable; explicit `not_found` and `ambiguous` negative/conflict examples must be tested. The proposed objective requires labelled questions before it is meaningful.
- **Stage 13 release:** obtain authorized representative Persian TXT, PDF-text and DOCX documents, including authentic minutes and multi-topic reports; aim for **30–50 documents and ≥100 labelled questions**, with independent human fact review and evidence review. Measure PDF RTL extraction and original-text anchor recall independently of summarization; include warm/cold CPU latency and peak memory. A production quality acceptance decision is **blocked** without this evidence.

## 6. Stage 9 acceptance evidence checklist

| Formal Stage 9 acceptance criterion | Result and evidence |
| --- | --- |
| Fixed, reproducible dataset and inspectable source quotes/configs | **Met:** versioned CC0 fixture, pinned real-document reference manifest, SHA-bound raw inference and review artifacts, exact source quotes, pinned model revision. |
| Reproduce three actual categories of failure | **Met:** short missing advice; multitopic direction inversion and missing topics; long repetitive education missing critical facts, all observed on the user's real pinned CPU mT5. |
| Clearly distinguish extraction from model/pipeline failure, with no false pass claims | **Met for evaluated text:** direct text, no extractor involved. **Not evaluated** on the original PDF; extraction error cannot be ruled out for that separate reported issue. |
| Record numerical next-stage stop/go gates and reference controls | **Met:** fixed synthetic and authentic dev metrics, critical reversals, repetition control and versioned Stage 10 seed gates above. |

**Engineering completion decision:** The fixed-scope **Stage 9 benchmark and diagnostic-baseline deliverable can be closed**, with explicitly recorded independent-review and representative-document **release** risks. This does **not** certify production model quality or complete the Stage 13 evaluation work. It does not authorize changing mT5 weights or silently running reserved holdouts.
