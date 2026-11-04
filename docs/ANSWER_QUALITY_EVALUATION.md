# Persian Document Query — Answer Quality Evaluation v1

**Date:** 2026-11-04
**Status:** Evaluation script, reference set and scorer tests prepared; real 34-question HTTP benchmark NOT RUN.
**Scope:** Source-exact Document Query answer mode only. No mT5 summarization change or Production signoff.

## Dataset, integrity and independence limits

- New assistant-authored synthetic, CC0, Persian TXT set: **8 documents, 34 questions**; 18 answerable, 12 not_found, four ambiguous.
- Logistics, clinic, finance, conditional safety and contradictions on date, amount, responsible person and percentage.
- Labels were defined before calling the new scorer and are not copied from Stage 11/13 fixtures or the prior user-local QA25 datasets.
- This is **not** independent human annotation, a genuine blind holdout or representative real-world Persian evaluation. Publication also makes future tuning against this fixture non-blind. It cannot establish a generic 8/9 quality rating.
- No private user material or local answer keys are committed. A SHA-256 of the fixture and local checkout commit are logged; a running server's Git revision cannot be verified automatically.

## Four metrics, fixed denominators

No HTTP failure is discarded. A zero denominator yields null, not 100%.

| Metric | Numerator | Denominator |
| --- | --- | --- |
| Answer Correctness | Returned answers with all labelled facts, exact source citations, and no status mismatch | All returned found answers, including false positives |
| False Positive Rate | Required abstentions where response was found or supplied an answer | All 16 expected not_found/ambiguous questions |
| Abstention Accuracy | Correct not_found with no evidence, or correct ambiguous with both cited conflicts | All 16 expected abstentions |
| Answer Completeness | Matched labelled atomic facts in grounded answers | All required atoms for 18 answerable questions |

Supporting metric: Found Question Success = full correct answers / 18 answerable questions.

Partial answers lower Completeness and are not fully Correct. False abstentions lower Completeness. Conflicts require two grounded quotations and a null answer. TXT source provenance additionally requires the real one-based source paragraph index, document type and source location type to agree with the cited text. Literal substring scoring is a conservative proxy for fact presence and original-source provenance, NOT a semantic entailment judge.

## Changed files

- benchmarks/fixtures/answer_quality_eval_v1.json: new fixed labelled synthetic documents and questions
- benchmarks/independent_answer_quality.py: strict data validation, source provenance, four metrics, local HTTP evaluator, append-only reporting
- tests/test_independent_answer_quality.py: pure metric, abstention, tampering and localhost-only endpoint tests
- docs/ANSWER_QUALITY_EVALUATION.md: methodology and reproducible steps
- docs/IMPLEMENTATION_PROGRESS.md: quality evaluation implementation record

No model, runtime code, REST schema, dependencies or frozen prior datasets changed.

## Verification boundary

Assistant isolated local copy: compileall PASS; scorer unit tests **19 passed**; fixture validation: **34 labelled questions**. This is not a full-repository pytest or live inference run.

Prior user Windows environment, unchanged runtime: **113 focused / 545 full tests passed**, 6/6 source-exact TXT/PDF/DOCX × two modes live smoke passed. These do NOT score the new 34 queries.

All four NEW quality metric values: **NOT RUN** against actual HTTP service. Production semantic quality gate: **NOT APPROVED**.

## Windows PowerShell verification

From repository root, with the existing .venv:

    git pull --ff-only origin main
    $env:env_type = "development"
    .\.venv\Scripts\python.exe -m pip check
    .\.venv\Scripts\python.exe -m compileall -q src benchmarks tests
    .\.venv\Scripts\python.exe -m pytest -q tests/test_independent_answer_quality.py
    .\.venv\Scripts\python.exe -m pytest -q
    .\.venv\Scripts\python.exe -m benchmarks.independent_answer_quality --validate-only

Start a local development server in terminal A, keeping the process running:

    .\.venv\Scripts\python.exe -m uvicorn src.host.app:app --host 127.0.0.1 --port 8001

In terminal B:

    .\.venv\Scripts\python.exe -m benchmarks.independent_answer_quality --base-url http://127.0.0.1:8001 --output .\local_answer_quality_eval_v1.json
    Get-Content -LiteralPath .\local_answer_quality_eval_v1.json -Raw

The report file is never overwritten. For repeated runs supply a distinct output path. The HTTP evaluator only sends synthetic data to localhost/127.0.0.1/[::1], never to an external host and never via a system proxy. HTTP failures count as invalid responses, rather than vanishing from denominators. On Linux/macOS, activate your venv and use python in place of the Windows executable path.

## Release decision

The evaluation instrument is reproducible; quality improvement remains unmeasured until a new run is examined. Before Production, run independent human-labelled Persian documents, review all missing/conflicting facts, validate Stage 10 factual requirements and complete security/operational release gates. Do not tune runtime against this new fixture if you intend to call it blind.


## First live 34-question evaluation — user-run Windows (2026-11-04)

**Observed Development result on local Uvicorn `127.0.0.1:8001` after fast-forward to commit `e8d2cb7cfa857be04cb630c4ebfb411eff11f535`:**

- `python -m pytest -q tests/test_independent_answer_quality.py`: **19 passed in 0.93s**.
- `python -m benchmarks.independent_answer_quality --validate-only`: **34 cases, eight documents** (18 found / 12 not_found / four ambiguous); user-reported fixture SHA-256 `4e6469a940ee196b93688a31cb194333eb5bb5f99b1b9d150fbf8d6417e4fde6`.
- Live benchmark invoked with `--base-url http://127.0.0.1:8001 --output .\\local_answer_quality_eval_v1.json`: **34 processed / zero invalid responses**; server logs showed 34 HTTP 200 responses. This is the first measured run of the new 34-case fixture.

| Metric | Observed numerator / denominator | Value |
| --- | ---: | ---: |
| Answer Correctness | 17 / 22 returned found | **77.27%** |
| False Positive Rate | 4 / 16 abstention-required | **25.00%** |
| Abstention Accuracy | 12 / 16 abstention-required | **75.00%** |
| Answer Completeness | 20 / 21 reference atoms | **95.24%** |
| Found Question Success | 17 / 18 answerable | **94.44%** |

Observed response statuses: **found=22, not_found=9, ambiguous=3**. The labels include only 18 answerable cases, and four of 16 cases requiring abstention instead returned a found/answer according to the scorer. Among 18 answerable cases, 17 had fully correct source-exact answers and one did not achieve full required-atom coverage. The recorded 20/21 atom coverage must not be interpreted as 20/21 independent documents or a semantic score.

**Unresolved root-cause evidence:** The user supplied aggregate output and HTTP logs, **not the report's per-case records**. Therefore the identities of the four false positives and the one incompletely answered question, and their precise source-level failure modes, are **NOT REVIEWED**. No runtime fix is justified merely from aggregate percentages. The synthetic references are public and cannot serve as an untouched holdout. Independent human-reviewed real-Persian evaluation, Stage 10 mT5 criteria, Docker/release security and Production semantic GO remain open; **Production NO-GO**.

To inspect the failed or incomplete cases in Windows PowerShell without revealing document contents:

```powershell
$report = Get-Content .\\local_answer_quality_eval_v1.json -Raw | ConvertFrom-Json
$report.records |
    Where-Object { $_.false_positive -eq $true -or $_.complete_and_correct -eq $false -or $_.abstention_correct -eq $false } |
    Select-Object id, expected_status, actual_status, expected_facts, matched_facts, false_positive, abstention_correct, conflict_evidence_supported |
    Format-Table -AutoSize
```

The JSON output is user-local and has not been committed. The next valid engineering step is to inspect these per-case records and their source evidence, then make *targeted* Answer Validation changes and validate them on a separate newly labelled human-reviewed set, not simply optimize the public fixture.


## Engineering remediation following v1 case-level inspection (2026-11-04)

The user provided five failed IDs with expected and actual statuses: **F05** found but one of two atomic answers missing; **F07** supplier-name false positive, **F08** wrong-month sales-rate false positive, **A04** two inconsistent same-period rates in TXT incorrectly returned found, and **N02** ticket price inferred from route-budget/passenger figures. These are source-grounded diagnosis targets, **not** newly measured results. The output from `local_answer_quality_eval_v1.json` must remain intact.

Minimal targeted Development patches to Answer Validation and document-query answer mode now require named supplier evidence rather than missing-value clauses, correct month/year and requested rate measure for percentage answers, explicit price-bearing facts for prices, same-metric conflict checks across TXT paragraphs, and bounded two-year same-metric evidence from separate TXT paragraphs. Prior DOCX/PDF source-neighborhood behavior and REST output remain unchanged. Eleven explicit/negative regression scenarios were added to `tests/test_answer_validation.py`.

**Post-fix real HTTP score: NOT RUN.** The previous 17/22, 4/16, 12/16 and 20/21 denominators are an immutable *before* baseline. Do not report improvement from tests alone or use this published fixture as a sealed human holdout.

From repository root on Windows PowerShell, with Development Uvicorn running on loopback:

```powershell
git pull --ff-only origin main
$env:env_type = "development"
.\.venv\Scripts\python.exe -m compileall -q src benchmarks tests
.\.venv\Scripts\python.exe -m pytest -q tests/test_answer_validation.py tests/test_stage11_retrieval.py tests/test_stage12_document_query.py tests/test_stage13_quality.py tests/test_independent_answer_quality.py
.\.venv\Scripts\python.exe -m pytest -q
# If Uvicorn is already serving the old code, stop/restart only that known Development server:
# .\.venv\Scripts\python.exe -m uvicorn src.host.app:app --host 127.0.0.1 --port 8001
.\.venv\Scripts\python.exe -m benchmarks.independent_answer_quality --base-url http://127.0.0.1:8001 --output .\local_answer_quality_eval_v2.json
$results = Get-Content .\local_answer_quality_eval_v2.json -Raw | ConvertFrom-Json
$results.metrics | Format-List
$results.records | Where-Object {
    $_.false_positive -eq $true -or
    $_.complete_and_correct -eq $false -or
    $_.abstention_correct -eq $false
} | Select-Object id, expected_status, actual_status, expected_facts, matched_facts,
    false_positive, abstention_correct, conflict_evidence_supported | Format-Table -AutoSize
```

Do not stop unrelated processes or overwrite the original report. Even with perfect new synthetic regression metrics, Production remains **NO-GO** until independent authorized Persian documents, human semantic labels, Stage 10 factual summarization gate and security/release criteria pass.


## v2 live quality results and residual regression fix (2026-11-04)

**User-measured `3068d5779d3f031ff9f991be2a2b63ad37211ca9` v2 synthetic HTTP baseline:** 34/34 valid responses; observed labels 18 found / 12 not_found / four ambiguous; Answer Correctness **18/18 100%**; False Positive Rate **0/16 0%**; Abstention Accuracy **16/16 100%**; Answer Completeness **21/21 100%**. This is a public synthetic regression, **not an untouched holdout or real-world semantic correctness certification**.

**Full-suite regression at that same revision:** 573 passed, **two failed**, two warnings. Focused suite: 141 passed, **two failed**, one warning. The failures were:
- `test_distinct_percentage_metrics_in_txt_are_not_conflicts`: sales-growth and customer-churn rates in the same period were incorrectly classified as conflicting because the candidate shared the company, period and "but" connector; it names a *different* rate measure.
- `test_stage12_multipart_stays_inside_original_txt_paragraph`: a legitimate two-part question about budget and "growth of it" was rejected because percentage validation required a topic word from the other half of the question in its percent clause.

A single targeted validator-only code change now excludes explicitly different rate measures from the conflicting-rate comparison, while preserving same-metric anaphoric conflicts; for amount+percentage multipart questions, percentage validation extracts measure terms from its percentage subquery only. Existing tests for all these distinctions are retained as regressions. This follow-up **has not yet been verified with full GitHub checkout pytest or a new live v3 benchmark**. No product, model, architecture, extraction/retrieval, API-schema or benchmark-fixture changes.

After pulling `main`, run on Windows PowerShell from the repository root:

```powershell
git pull --ff-only origin main
$env:env_type = "development"
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m compileall -q src tests benchmarks
.\.venv\Scripts\python.exe -m pytest -q tests/test_answer_validation.py tests/test_stage11_retrieval.py tests/test_stage12_document_query.py tests/test_stage13_quality.py tests/test_independent_answer_quality.py
.\.venv\Scripts\python.exe -m pytest -q
# Restart only the known, existing Development Uvicorn on port 8001 if needed.
# In a second terminal while Uvicorn is serving the updated code:
.\.venv\Scripts\python.exe -m benchmarks.independent_answer_quality --base-url http://127.0.0.1:8001 --output .\local_answer_quality_eval_v3.json
$report = Get-Content .\local_answer_quality_eval_v3.json -Raw | ConvertFrom-Json
$report.metrics | Format-List
```

Compare against the immutable v2 before claiming improvement. **Production stays NO-GO** pending real-world independently adjudicated Persian documents, original Stage 10 summarization thresholds and security/operational release checks.
