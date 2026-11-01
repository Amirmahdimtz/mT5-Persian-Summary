# Stage 9 — Persian Summarization Quality Benchmark & Root-Cause Record

**Status:** Benchmark tooling implemented; **real-model baseline and human review pending**. This document is not evidence of improved model accuracy or completion of Stage 9 acceptance.

## Objective and scope

Reproduce and measure the existing general summarizer's shortcomings without changing model parameters, inference, API, text extraction, or the eight completed MVP stages. The Stage 9 dataset is an **initial synthetic seed**, not a representative sample of user documents. Stage 10 must not make a quality-improvement claim based only on these samples.

## Inputs and provenance

- Dataset: `benchmarks/fixtures/quality_v1.json` (`version=1`, `license=CC0-1.0`). All seven cases are original synthetic Persian examples prepared for this repository; none contain user/private documents. Five are `dev`, two are `holdout`.
- Seed coverage: short weather news; a multi-topic case based on the known pollution-direction issue; a repeated long education story based on the Stage 8 smoke; a synthetic meeting with person/date/budget facts; a quarterly costs report; separate held-out meeting and news cases.
- Every source fact includes a verbatim `source_quote` located in the actual expanded source text and a fact type (`date`, `person`, `number`, `direction`, `topic`, `action`). `reference_summary` is written by a human, **not** automatically comparable as a correct model score.
- `repeat` expands only a small, bounded text for long-input testing. It is not a claim that the repeated article is representative of complex long documents.
- The previously reported eight-page PDF with 18,052 extracted characters is **not included**: its bytes and permission to redistribute have not been provided. Do not reconstruct it or pretend to have reproduced it.

## Baseline workflow (Windows PowerShell)

Run from the root of the Git checkout in the already configured Python 3.12 virtual environment. **Create a new file name for each run**: the tool never overwrites previous artifacts. Raw run results and review annotations may contain sensitive text and must not be committed.

```powershell
git pull --ff-only origin main
.\.venv\Scripts\Activate.ps1
$env:env_type = 'development'
python -m pip check
python -m benchmarks.quality_benchmark validate
python -m pytest -q tests/test_quality_benchmark.py
python -m benchmarks.quality_benchmark run --split dev --output local_quality_dev_run1.json
python -m benchmarks.quality_benchmark review-template --runs local_quality_dev_run1.json --output local_quality_dev_review1.json
```

Edit `local_quality_dev_review1.json` in a text editor. For **every** expected fact set `label` to `covered`, `omitted` or `distorted`; examine the original document, not just whether a word appears in the summary. Decompose generated text into **atomic factual claims**. For each claim set `supported=true` with an exact `evidence_quote` from the input, or `supported=false` with no evidence. The tool checks that positive evidence is truly a source substring; **a human must still judge whether it entails the claim**. Do not use the automatic metric as a substitute for review. Then run:

```powershell
python -m benchmarks.quality_benchmark score --runs local_quality_dev_run1.json --reviews local_quality_dev_review1.json --output local_quality_dev_metrics1.json
```

After fixing the evaluation method and **before** using holdout for model selection, the designated reviewer can run:

```powershell
python -m benchmarks.quality_benchmark run --split holdout --output local_quality_holdout_run1.json
```

To inspect PDF RTL/text extraction separately from inference, prepare a UTF-8 text file containing one exact phrase per line that is known to appear in the original PDF, and run:

```powershell
python -m benchmarks.quality_benchmark inspect-extraction --file "sample.pdf" --anchors "anchors.txt" --output "local_extraction_diagnostic1.json"
```

No OCR is performed; the `anchors` must come from the original source or approved human transcription. Extraction diagnostics reveal exact text-preservation issues, **not** summarization/model failures.

## Interpreting measures

| Measure | Calculation | Caveat |
| --- | --- | --- |
| `fact_coverage` | Manually marked `covered` facts / all reviewed facts | **Only reviewed runs**; no semantic automatic metric |
| `fact_distortion_rate` | Manually marked `distorted` facts / all reviewed facts | Review each date, number, person and change direction |
| `unsupported_claim_rate` | Manually marked unsupported atomic claims / all reviewed claims | Missing claims, incomplete review or weak evidence undermine validity |
| `by_fact_type` | Review counts for date/person/number/direction/topic/action | Subgroup size must be reported |
| `length_diagnostics` | Mean output characters by requested tier | Length is not an accuracy or compliance guarantee |
| `identical_output_across_tiers` | Cases whose generated summaries exactly match for multiple tiers | Only a diagnostic signal; short source may justifiably match |
| `elapsed_seconds` | Wall time of each real-model call | Machine, cache state and inference contention affect result |
| `exact_anchor_recall` | Exact anchors found / provided anchors | Approximate diagnosis of extraction/RTL only |

`reviewed_runs`, `unreviewed_successful_runs` and failed model calls must be checked before comparing runs. Partially reviewed results are **not** an overall baseline. No metric is reported as a measured result until actual mT5 output and human review are supplied.

## Root-cause inventory (hypotheses, not confirmed fixes)

| Observation/evidence | Candidate cause | Disambiguating test |
| --- | --- | --- |
| Historic multi-topic smoke omitted health/education facts and inverted pollution *decrease* to *increase* | mT5 factual fidelity and content-selection limitations; optional reduction-stage loss | Compare source, single-chunk and long reduction outputs; manually annotate fact types |
| Historic real eight-page PDF: `medium` and `long` identical 113-character summaries | Early decoder stopping; generation configured with maximum budgets instead of length targets; intermediate reduction may discard details | Run the same lawful PDF with raw extracted text and source anchors; compare output token lengths and tiers; preserve original artifact |
| Long repeated education story produced extremely terse summary | Repetitive input and lossy hierarchical map/reduce; model training-domain mismatch | Compare repeated and non-repeated versions, inspect intermediate summaries with a development-only diagnostic |
| PDF Persian RTL text can be in visual rather than logical order | PDF text-layer extraction, distinct from model generation | Check human-known anchors and original PDF against extracted text *before* inference |
| Document Query endpoint not yet present | Not a Stage 9 bug | Retrieval/structured evidence belongs to Stages 11–12 |

**Known existing limits:** the current service uses max 1,000 mT5 input tokens per chunk, up to 64 chunks, at most six hierarchy levels and 128 calls, and output caps of 40/80/120 tokens; these limits are documented constraints, not measured Stage 9 discoveries. No runtime service or generation settings are changed in this Stage.

## Stop/go criteria to freeze before Stage 10

1. Collect a representative, legally usable set of **30–50 documents** and, for later retrieval stages, at least **100 annotated questions**, plus a truly held-out test group. The seven-case seed is insufficient for definitive acceptance.
2. Execute the current pinned model baseline on all required tiers, store dataset SHA-256, model ID/revision/settings, hardware and elapsed time, and manually annotate all required facts and claims. Record the raw and reviewed artifact paths without publishing private contents.
3. Review PDF text quality separately where PDFs are available; classify failures as extraction, chunking, hierarchical reduction or generation with evidence rather than guesswork.
4. Before tuning Stage 10, freeze acceptance thresholds on the representative development set. Proposed decision direction: **higher Fact Coverage without higher Unsupported Claim Rate or Date/Person/Number Distortion**. No numerical improvement target is yet validated; thresholds must be selected using actual baseline, sample sizes and reviewer agreement.
5. If model weights, original PDF, or authorized reviewers are unavailable, Stage 9 status remains **In Progress / Blocked for real-model baseline**, not Completed.

## Results recorded in the authoring environment

- `python -m pytest -q tests/test_quality_benchmark.py`: **23 passed** in isolated tooling workspace.
- `python -m compileall -q benchmarks tests`: **passed** in isolated tooling workspace.
- `python -m benchmarks.quality_benchmark validate`: **passed**, seven cases, `dev=5`, `holdout=2`.
- `python -m benchmarks.quality_benchmark run` with the **real** mT5 model: **Not Run**, no working full checkout or Transformers/checkpoint access in the execution sandbox. Mock-injected test wiring is not real inference.
- End-to-end old 266-test suite, source extraction on the user's actual PDF, full-size quality dataset, and manual factual reviews: **Not Run / Not Available** in this environment.

These results must be updated with actual user-side baseline output before the stage is called Completed. Do not commit raw local output/review files; run them in a private directory or keep the `local_quality_*` files untracked.

## User-side baseline evidence — 2026-11-01

The user executed the Stage 9 benchmark on Windows 11, Python 3.12.10, CPU, with the pinned model `nafisehNik/mt5-persian-summary` at revision `b575560ad967050e77a40f907abb1ebbeefb9a15`. These are **observed user-submitted results**, not reproduced in the assistant execution environment.

- Targeted tests: **23 passed** in 3.42 seconds.
- Entire project regression suite: **289 passed, 2 nonblocking deprecation warnings** in 15.42 seconds; this confirms compatibility but does not establish semantic correctness.
- Dataset validation: **7 cases; dev=5, holdout=2**, SHA-256 `cc907d6b16a4b68685b280002bb0a0f550ce6ce3966941c8732702c016f8a9a9`.
- Real model run: **15 successful results, 0 reported model errors** (5 development cases × 3 length tiers). The user generated `local_quality_dev_run1.json` and a separate unreviewed template. Do not commit those local artifacts.
- All **5/5 development cases** produced **exactly identical text** for `short`, `medium` and `long`. Output token counts (including specials) ranged **19–33**, below configured generation ceilings of 40/80/120.
- Recorded end-to-end per-call elapsed time totaled **253.064 seconds** across 15 calls, including a **114.048-second first call** (likely model loading/cold start, not proven). These timings are not comparable CPU latency benchmarks without controlled warm-up and environment normalization.
- Qualitative fact checks against the versioned source: `multitopic_pollution` inverted the intended **decrease** in pollution into an **increase**; `budget_report` inverted an expense **increase** from 30 to 36 million into a **decrease**; `meeting_decisions` retained the first meeting date but omitted owners, deadlines, next meeting and the budget. The education and weather cases also omitted essential listed facts. These are **model-output observations**, not PDF extraction results.
- A provisional **assistant-proposed** fact/claim annotation (not yet independently human-verified) gives **3/19 covered facts (15.8%), 2/19 distorted facts (10.5%), 14/19 omitted facts (73.7%) per tier**. Across the three identical tiers, this becomes 9/57, 6/57 and 42/57; these are repeated observations, **not 57 independent facts**. Provisional unsupported atomic claims are **3/8 (37.5%) per tier**; the `weather_short` “warning” claim is judgement-sensitive. These metrics must **not** be frozen as the representative accepted quality baseline before reviewer sign-off.
- **Not measured:** peak RAM, actual eight-page PDF extraction, representative 30–50-document dataset, independent human review, and held-out model results. The 2-case holdout remains unrun for model-tuning purposes.

**Status remains In Progress.** The initial real-model seed run and full code regression are confirmed, while Stage 9 acceptance still depends on human-confirmed labels, representative sources and agreed Stage 10 go/no-go thresholds.

## Stage 9 follow-up: five-case audit, reference corpus and provisional gates (2026-11-01)

- See [STAGE9_SEED_AUDIT_AND_GATES.md](STAGE9_SEED_AUDIT_AND_GATES.md) for a case-by-case factual audit of the **five unique** user-generated mT5 outputs, exact fact-label tallies, ambiguous weather-warning wording and proposed Stage 10 quantitative thresholds.
- A new pinned **reference-only real corpus manifest**, `benchmarks/fixtures/real_project_documents_v1.json`, references three authentic in-repository Persian documents without embedding their content or claiming CC0 ownership. It is materialized with `python -m benchmarks.project_document_dataset --output local_quality_project_v1.json` and then evaluated through `python -m benchmarks.quality_benchmark --dataset local_quality_project_v1.json ...`. It includes two dev cases and one reserved holdout.
- Local authoring-environment checks: **32 passed** for original Stage 9 and new manifest tests; **no model inference** on the new documents yet. Two available authentic document byte hashes and evidence phrases were validated locally; the third document's Git blob and source snippets were checked against GitHub, but complete corpus preparation must run in a real cloned repository.
- **No authentic independent meeting minutes, original text-based PDF or DOCX are attached/available**. The real repository sources are Markdown, not a substitute for PDF extraction diagnosis. A representative external-document benchmark and independent sign-off remain blockers.
- The proposed seed gates (**≥8/19 covered, zero two critical inversions, ≤12.5% unsupported claims, ≥3/5 length differentiation**) are diagnostic **pre-tuning targets**, not production acceptance thresholds until reviewed and extended to representative real documents.
- **Status remains In Progress**; no Stage 10 production pipeline or model configuration has been changed.
