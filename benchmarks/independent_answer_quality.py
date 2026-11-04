"""Reproducible, source-grounded Persian Document Query evaluation (no model calls).

Synthetic labels are authored before inference and must never be tuned against
this run. Exact-match atomic facts are a conservative proxy, NOT semantic entailment
or independent human review. Reports omit the source and answer text.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

import httpx

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "answer_quality_eval_v1.json"
_STATUSES = frozenset({"found", "not_found", "ambiguous"})


class EvaluationInputError(ValueError):
    """The benchmark, endpoint or model response violates the evaluation contract."""


def load_fixture(path: Path) -> dict:
    raw = path.read_bytes()
    fixture = json.loads(raw)
    if not isinstance(fixture, dict) or fixture.get("version") != 1 or fixture.get("split") != "evaluation":
        raise EvaluationInputError("Unsupported evaluation fixture version or split")
    docs = fixture.get("documents")
    cases = fixture.get("cases")
    if not isinstance(docs, list) or not 1 <= len(docs) <= 100 or not isinstance(cases, list) or not 1 <= len(cases) <= 2000:
        raise EvaluationInputError("Invalid document or case count")
    document_map = {}
    for doc in docs:
        if (not isinstance(doc, dict) or not isinstance(doc.get("id"), str)
                or not isinstance(doc.get("text"), str) or not doc["text"].strip()
                or len(doc["text"]) > 100_000 or not isinstance(doc.get("filename"), str)
                or not doc["filename"].endswith(".txt") or "/" in doc["filename"]
                or "\\" in doc["filename"] or doc["id"] in document_map):
            raise EvaluationInputError("Malformed or duplicate TXT fixture document")
        document_map[doc["id"]] = doc
    ids = set()
    for case in cases:
        if not isinstance(case, dict):
            raise EvaluationInputError("Malformed case")
        cid, docid, query, status = (case.get(k) for k in ("id", "document_id", "query", "status"))
        facts = case.get("facts")
        quotes = case.get("competing_quotes", [])
        if (not isinstance(cid, str) or not cid or cid in ids
                or not isinstance(docid, str) or docid not in document_map
                or not isinstance(query, str) or not query.strip() or len(query) > 512
                or not isinstance(status, str) or status not in _STATUSES
                or not isinstance(facts, list) or any(not isinstance(f, str) or not f for f in facts)
                or not isinstance(quotes, list) or any(not isinstance(q, str) or not q for q in quotes)):
            raise EvaluationInputError("Malformed or duplicate evaluation case")
        ids.add(cid)
        text = document_map[docid]["text"]
        if ((status == "found" and (not facts or quotes))
                or (status != "found" and facts)
                or (status == "ambiguous" and len(quotes) < 2)
                or (status != "ambiguous" and quotes)
                or any(f not in text for f in facts)
                or any(q not in text for q in quotes)):
            raise EvaluationInputError("Reference facts or conflict quotes disagree with source")
    return fixture


def validate_base_url(value: str) -> str:
    """Never submit benchmark documents to an unexpected remote address."""
    parsed = urlsplit(value)
    if (parsed.scheme != "http" or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
            or parsed.username is not None or parsed.password is not None
            or parsed.path not in ("", "/") or parsed.query or parsed.fragment):
        raise EvaluationInputError("base-url must be a local plain-HTTP origin")
    try:
        port = parsed.port
    except ValueError as exc:
        raise EvaluationInputError("Invalid base-url port") from exc
    if port is None:
        raise EvaluationInputError("Explicit local port required")
    return value.rstrip("/")


def evaluate_case(case: dict, doc: dict, payload: dict | None, *, http_ok: bool = True) -> dict:
    """Score label-matched facts, strict original-source provenance and abstentions."""
    expected = case["status"]
    status = payload.get("status") if isinstance(payload, dict) else None
    answer = payload.get("answer") if isinstance(payload, dict) else None
    evidence = payload.get("evidence") if isinstance(payload, dict) else None
    valid_response = (http_ok and status in _STATUSES
                      and (answer is None or isinstance(answer, str))
                      and isinstance(evidence, list)
                      and all(isinstance(item, dict) and isinstance(item.get("text"), str)
                              for item in evidence))
    source = doc["text"]
    texts = [item["text"] for item in evidence] if valid_response else []
    grounded = bool(valid_response and texts and all(t and t in source for t in texts)
                    and answer == "\n".join(texts))
    valid_empty = bool(valid_response and answer is None and not texts)
    expected_facts = case["facts"]
    matched = sum(fact in answer for fact in expected_facts) if expected == "found" and status == "found" and grounded else 0
    complete = bool(expected == "found" and status == "found" and grounded
                    and matched == len(expected_facts))
    conflict_supported = bool(
        valid_response and status == "ambiguous" and answer is None
        and texts and all(t and t in source for t in texts)
        and all(any(quote in t for t in texts) for quote in case.get("competing_quotes", []))
    )
    abstention_correct = bool(
        (expected == "not_found" and status == "not_found" and valid_empty)
        or (expected == "ambiguous" and conflict_supported)
    )
    false_positive = bool(expected != "found" and valid_response
                          and (status == "found" or answer is not None))
    return {
        "id": case["id"], "expected_status": expected,
        "actual_status": status if valid_response else "invalid_response",
        "source_grounded": grounded if status == "found" else None,
        "complete_and_correct": complete if expected == "found" else None,
        "expected_facts": len(expected_facts), "matched_facts": matched,
        "abstention_correct": abstention_correct if expected != "found" else None,
        "false_positive": false_positive if expected != "found" else None,
        "conflict_evidence_supported": conflict_supported if expected == "ambiguous" else None,
    }


def score_records(records: list[dict]) -> dict:
    answered = [r for r in records if r["actual_status"] == "found"]
    answerable = [r for r in records if r["expected_status"] == "found"]
    abstain = [r for r in records if r["expected_status"] != "found"]
    counters = Counter(r["actual_status"] for r in records)

    def metric(numerator: int, denominator: int) -> dict:
        return {"numerator": numerator, "denominator": denominator,
                "value": round(numerator / denominator, 6) if denominator else None}

    return {
        "cases": len(records), "status_distribution": dict(counters),
        "answer_correctness": metric(sum(r["complete_and_correct"] is True for r in answered), len(answered)),
        "false_positive_rate": metric(sum(r["false_positive"] is True for r in abstain), len(abstain)),
        "abstention_accuracy": metric(sum(r["abstention_correct"] is True for r in abstain), len(abstain)),
        "answer_completeness": metric(sum(r["matched_facts"] for r in answerable),
                                      sum(r["expected_facts"] for r in answerable)),
        "found_question_success": metric(sum(r["complete_and_correct"] is True for r in answerable), len(answerable)),
        "invalid_responses": counters.get("invalid_response", 0),
    }


def _git_sha() -> str | None:
    result = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False)
    return result.stdout.strip() if result.returncode == 0 else None


def run(*, fixture_path: Path, base_url: str, output: Path, timeout: float = 30.0) -> dict:
    fixture = load_fixture(fixture_path)
    endpoint = validate_base_url(base_url) + "/api/v1/document_query/file"
    if not 0 < timeout <= 180:
        raise EvaluationInputError("timeout must be between 0 and 180 seconds")
    if output.exists():
        raise FileExistsError(f"Report exists; refusing to overwrite: {output}")
    docs = {doc["id"]: doc for doc in fixture["documents"]}
    records = []
    # No proxy forwarding, environment credentials, or redirects for local eval.
    with httpx.Client(timeout=timeout, trust_env=False, follow_redirects=False) as client:
        for case in fixture["cases"]:
            doc = docs[case["document_id"]]
            try:
                response = client.post(endpoint, files={"file": (
                    doc["filename"], doc["text"].encode("utf-8"), "text/plain")},
                    data={"query": case["query"], "mode": "answer"})
                payload = response.json() if response.status_code == 200 else None
                record = evaluate_case(case, doc, payload, http_ok=response.status_code == 200)
                if response.status_code != 200:
                    record["http_status"] = response.status_code
            except (httpx.RequestError, ValueError) as exc:
                record = evaluate_case(case, doc, None, http_ok=False)
                record["error_type"] = type(exc).__name__  # Avoid source or query leakage.
            records.append(record)
    report = {
        "benchmark": "answer_quality_eval_v1", "split": "evaluation",
        "source": "new assistant-authored synthetic fixture; not independent human/real-document test",
        "fixture_sha256": hashlib.sha256(fixture_path.read_bytes()).hexdigest(),
        "git_commit": _git_sha(), "server_commit_verified": False,
        "endpoint": endpoint, "metrics": score_records(records), "records": records,
        "independent_human_semantic_review": "NOT_RUN",
        "production_semantic_quality_gate": "NOT_APPROVED",
    }
    # Store no raw private source or answer. Existing outputs never overwritten.
    with output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, default=FIXTURE)
    parser.add_argument("--base-url", help="Loopback HTTP server, e.g. http://127.0.0.1:8001")
    parser.add_argument("--output", type=Path, help="New report JSON path (never overwritten)")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    try:
        fixture = load_fixture(args.fixture)
        if args.validate_only:
            print(json.dumps({"validated_cases": len(fixture["cases"]),
                              "documents": len(fixture["documents"]),
                              "status_labels": dict(Counter(c["status"] for c in fixture["cases"])),
                              "sha256": hashlib.sha256(args.fixture.read_bytes()).hexdigest()},
                             ensure_ascii=False, indent=2))
            return 0
        if not args.base_url or not args.output:
            parser.error("--base-url and --output required except for --validate-only")
        report = run(fixture_path=args.fixture, base_url=args.base_url, output=args.output,
                     timeout=args.timeout)
        print(json.dumps(report["metrics"], ensure_ascii=False, indent=2))
        return 0 if report["metrics"]["invalid_responses"] == 0 else 1
    except (EvaluationInputError, ValueError, FileExistsError, OSError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
