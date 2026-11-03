"""Fail-closed, evidence-bound Production readiness screen (never grants GO).

No model loading or network access. Human/semantic release approval remains a
separate signed decision; even all green inputs yield MANUAL_SIGNOFF_REQUIRED.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any

STAGE13_DEV_SHA256 = "e169b6d2e3f4196c05c93a5c80dcf617af14438922a206ef03d4ce4e3a88824c"
STAGE11_LABELS_SHA256 = "7fa910edc47c98f712d0f9f83eb646998f7eb859c4a4d2e42153ad524c6e770e"
STAGE9_DEV_SHA256 = "cc907d6b16a4b68685b280002bb0a0f550ce6ce3966941c8732702c016f8a9a9"


class ReleaseEvidenceError(ValueError):
    """Invalid evidence: fail closed without ever copying source text into reports."""


def _load(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    # Reports contain metrics only. Private source/evidence is never echoed.
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ReleaseEvidenceError("evidence JSON root must be an object")
    return value


def _ratio(value: Any) -> bool:
    return type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 1


def _integer(value: Any, low: int, high: int = 100_000) -> bool:
    return type(value) is int and low <= value <= high


def _stage13_ok(metrics: dict[str, Any] | None) -> bool:
    if not isinstance(metrics, dict):
        return False
    required = {
        "query_fixture_sha256": STAGE13_DEV_SHA256,
        "stage11_dev_labels_sha256": STAGE11_LABELS_SHA256,
        "stage9_dev_dataset_sha256": STAGE9_DEV_SHA256,
        "split": "dev",
        "stage11_queries": 15,
        "stage12_queries": 11,
        "stage10_frozen_semantic_quality_gate": "NOT_RETESTED",
        "production_semantic_quality_gate": "NOT_APPROVED",
    }
    if any(metrics.get(key) != value for key, value in required.items()):
        return False
    score_keys = (
        "stage11_recall_at_1", "stage11_recall_at_3", "status_accuracy",
        "answer_exact_match", "evidence_support_rate", "no_answer_accuracy",
        "ambiguous_detection", "focused_coverage",
    )
    if any(not _ratio(metrics.get(key)) or metrics[key] != 1.0 for key in score_keys):
        return False
    records = metrics.get("records")
    if not isinstance(records, list) or len(records) != 11:
        return False
    if not all(isinstance(item, dict) and isinstance(item.get("id"), str)
               and item.get("status_match") is True for item in records):
        return False
    return len({item["id"] for item in records}) == 11


def _model_ok(model: dict[str, Any] | None) -> bool:
    if not isinstance(model, dict) or model.get("status") != "STRUCTURAL_PASS":
        return False
    if model.get("model_inference_exercised") is not True:
        return False
    if not isinstance(model.get("container_image_id"), str) or not (
        len(model["container_image_id"]) == 71
        and model["container_image_id"].startswith("sha256:")
        and all(c in "0123456789abcdef" for c in model["container_image_id"][7:])
    ):
        return False
    snapshot = model.get("dependency_snapshot")
    if (not isinstance(snapshot, dict) or snapshot.get("status") != "MATCH"
            or snapshot.get("pin_count") != 48 or snapshot.get("mismatch_names") != []):
        return False
    observations = model.get("observations")
    if not isinstance(observations, list) or len(observations) < 2:
        return False
    phases = [row.get("phase") for row in observations if isinstance(row, dict)]
    if "first_observed" not in phases or "warm_repeat" not in phases:
        return False
    if not all(isinstance(row, dict) and row.get("http_status") == 200
               and _integer(row.get("summary_characters"), 1, 200_000)
               and type(row.get("elapsed_ms")) in (int, float)
               and math.isfinite(row["elapsed_ms"]) and row["elapsed_ms"] >= 0
               for row in observations):
        return False
    after = model.get("memory_after")
    if not isinstance(after, dict):
        return False
    peak, limit = after.get("peak_bytes"), after.get("limit_bytes")
    return (_integer(peak, 1, 2**63 - 1) and _integer(limit, 1, 2**63 - 1)
            and peak <= limit)


def _review_ok(review: dict[str, Any] | None, evidence_hash: str | None) -> bool:
    if not isinstance(review, dict) or review.get("schema_version") != 1:
        return False
    if review.get("review_scope") != "authorized_real_persian_documents":
        return False
    if (not _integer(review.get("documents_reviewed"), 30)
            or not _integer(review.get("labeled_questions"), 100)):
        return False
    reviewers = review.get("independent_reviewer_ids")
    if (not isinstance(reviewers, list) or len(reviewers) < 2
            or any(not isinstance(x, str) or not 1 <= len(x) <= 128 for x in reviewers)
            or len(set(reviewers)) != len(reviewers)):
        return False
    if (review.get("independent_review_approved") is not True
            or review.get("security_review_approved") is not True):
        return False
    if (not isinstance(evidence_hash, str)
            or review.get("review_evidence_sha256") != evidence_hash):
        return False
    recall = review.get("representative_retrieval_recall_at_3")
    if not _ratio(recall) or recall < 0.90:
        return False
    frozen = review.get("stage10_frozen_development_gates")
    if not isinstance(frozen, dict):
        return False
    return (
        frozen.get("synthetic_medium_fact_total") == 19
        and _integer(frozen.get("synthetic_medium_facts_covered"), 8, 19)
        and _integer(frozen.get("critical_direction_inversions"), 0, 0)
        and _integer(frozen.get("synthetic_medium_fact_distortions"), 0, 0)
        and _ratio(frozen.get("synthetic_unsupported_claim_rate"))
        and frozen["synthetic_unsupported_claim_rate"] <= 0.125
        and _integer(frozen.get("distinct_short_long_case_count"), 3, 5)
        and frozen.get("real_project_medium_fact_total") == 6
        and _integer(frozen.get("real_project_medium_facts_covered"), 3, 6)
        and _integer(frozen.get("critical_fabricated_facts"), 0, 0)
        and _ratio(frozen.get("architecture_duplicate_fourgram_fraction"))
        and frozen["architecture_duplicate_fourgram_fraction"] == 0
    )


def assess(
    development: dict[str, Any] | None,
    model: dict[str, Any] | None,
    independent_review: dict[str, Any] | None,
    *,
    review_evidence_sha256: str | None = None,
    visibility: str = "private_loopback",
) -> dict[str, Any]:
    """Machine-readable screen; a passing screen is never production signoff."""
    if visibility not in ("private_loopback", "public"):
        raise ReleaseEvidenceError("visibility must be private_loopback or public")
    checks = {
        "frozen_development_metrics": _stage13_ok(development),
        "real_model_http_and_cgroup_memory": _model_ok(model),
        "independent_real_document_review": _review_ok(independent_review, review_evidence_sha256),
        # This service has no native auth/rate limiting: public deployment
        # requires an independently reviewed gateway/security architecture.
        "private_only_deployment": visibility == "private_loopback",
    }
    return {
        "schema_version": 1,
        "decision": "MANUAL_SIGNOFF_REQUIRED" if all(checks.values()) else "NO_GO",
        "production_go": False,
        "checks": checks,
        "blocked_checks": [key for key, value in checks.items() if not value],
        "stage10_frozen_real_medium_minimum": "3/6 (last independently unapproved assessment: 2/6)",
        "limitations": (
            "Synthetic metrics are not semantic accuracy. Human reviewer metadata and "
            "evidence hashes are user-provided attestations, not cryptographic proof "
            "of reviewer independence. This program never authorizes production."
        ),
    }



def _file_sha256(path: Path) -> str:
    """Hash review evidence without buffering potentially large private files."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(64 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--development-report", type=Path)
    parser.add_argument("--model-report", type=Path)
    parser.add_argument("--human-review", type=Path)
    parser.add_argument("--review-evidence", type=Path,
                        help="Local private review record; bytes hashed, never copied to output")
    parser.add_argument("--visibility", choices=("private_loopback", "public"),
                        default="private_loopback")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        evidence_sha = _file_sha256(args.review_evidence) if args.review_evidence else None
        result = assess(
            _load(args.development_report), _load(args.model_report),
            _load(args.human_review), review_evidence_sha256=evidence_sha,
            visibility=args.visibility,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8", newline="\n") as output:
            json.dump(result, output, ensure_ascii=False, sort_keys=True, indent=2)
            output.write("\n")
    except (OSError, ValueError, json.JSONDecodeError) as error:
        parser.exit(2, f"Production gate input/output failed: {type(error).__name__}\n")
    print(f"Production decision: {result['decision']} (never automatic GO); report: {args.output}")
    # Make the exit unsuitable as an automated release/publish success signal.
    return 2 if result["decision"] == "NO_GO" else 3


if __name__ == "__main__":
    sys.exit(main())
