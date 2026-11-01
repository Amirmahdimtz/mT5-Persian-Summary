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

- `python -m pytest -q tests/test_quality_benchmark.py`: **21 passed** in isolated tooling workspace.
- `python -m compileall -q benchmarks tests`: **passed** in isolated tooling workspace.
- `python -m benchmarks.quality_benchmark validate`: **passed**, seven cases, `dev=5`, `holdout=2`.
- `python -m benchmarks.quality_benchmark run` with the **real** mT5 model: **Not Run**, no working full checkout or Transformers/checkpoint access in the execution sandbox. Mock-injected test wiring is not real inference.
- End-to-end old 266-test suite, source extraction on the user's actual PDF, full-size quality dataset, and manual factual reviews: **Not Run / Not Available** in this environment.

These results must be updated with actual user-side baseline output before the stage is called Completed. Do not commit raw local output/review files; run them in a private directory or keep the `local_quality_*` files untracked.
