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
