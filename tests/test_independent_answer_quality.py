"""Pure scoring-contract tests: no real HTTP service and no tuned expected outputs."""

from __future__ import annotations

import copy

import pytest

from benchmarks.independent_answer_quality import (
    EvaluationInputError, FIXTURE, evaluate_case, load_fixture,
    score_records, validate_base_url,
)


def case(status, facts=(), quotes=()):
    return {"id": "q1", "status": status, "facts": list(facts),
            "competing_quotes": list(quotes)}


DOC = {"text": "بودجه پروژه ۳۵۰ میلیون بود.\n\nبودجه پروژه ۴۰۰ میلیون بود."}


def result(status, text=None, evidence=None):
    paragraphs = DOC["text"].split("\n\n")
    return {"status": status, "answer": text,
            "evidence": [{"text": quote, "document_type": "txt",
                          "location_type": "paragraph", "paragraph": paragraphs.index(quote) + 1,
                          "page": None} for quote in (evidence or [])]}


def test_fixed_fixture_is_valid_and_covers_all_classes():
    data = load_fixture(FIXTURE)
    assert len(data["documents"]) == 8
    assert len(data["cases"]) == 34
    assert {x["status"] for x in data["cases"]} == {"found", "not_found", "ambiguous"}


def test_complete_source_grounded_answer_is_correct():
    text = "بودجه پروژه ۳۵۰ میلیون بود."
    row = evaluate_case(case("found", ["۳۵۰ میلیون"]), DOC,
                        result("found", text, [text]))
    assert row["complete_and_correct"] is True and row["matched_facts"] == 1


def test_partial_answer_lowers_completeness_and_correctness():
    text = "بودجه پروژه ۳۵۰ میلیون بود."
    row = evaluate_case(case("found", ["۳۵۰ میلیون", "۴۰۰ میلیون"]), DOC,
                        result("found", text, [text]))
    assert row["matched_facts"] == 1 and row["complete_and_correct"] is False
    metrics = score_records([row])
    assert metrics["answer_correctness"]["value"] == 0
    assert metrics["answer_completeness"]["value"] == 0.5


def test_hallucinated_text_cannot_pass_grounding():
    row = evaluate_case(case("found", ["۳۵۰ میلیون"]), DOC,
                        result("found", "۳۵۰ میلیون دروغین", ["بودجه پروژه ۳۵۰ میلیون بود."]))
    assert not row["source_grounded"] and not row["complete_and_correct"]


def test_valid_not_found_and_correct_ambiguity():
    n = evaluate_case(case("not_found"), DOC, result("not_found"))
    a = evaluate_case(case("ambiguous", quotes=["۳۵۰ میلیون", "۴۰۰ میلیون"]), DOC,
                      result("ambiguous", None, ["بودجه پروژه ۳۵۰ میلیون بود.",
                                                  "بودجه پروژه ۴۰۰ میلیون بود."]))
    metrics = score_records([n, a])
    assert metrics["abstention_accuracy"]["value"] == 1.0
    assert metrics["false_positive_rate"]["value"] == 0.0


def test_wrong_conflict_evidence_is_not_accurate_abstention():
    row = evaluate_case(case("ambiguous", quotes=["۳۵۰ میلیون", "۴۰۰ میلیون"]), DOC,
                        result("ambiguous", None, ["بودجه پروژه ۳۵۰ میلیون بود."]))
    assert not row["abstention_correct"]


def test_found_on_should_abstain_counts_false_positive():
    row = evaluate_case(case("not_found"), DOC,
                        result("found", "بودجه پروژه ۳۵۰ میلیون بود.", ["بودجه پروژه ۳۵۰ میلیون بود."]))
    metrics = score_records([row])
    assert metrics["false_positive_rate"]["value"] == 1.0
    assert metrics["abstention_accuracy"]["value"] == 0.0


def test_wrong_abstention_for_answerable_is_incomplete():
    row = evaluate_case(case("found", ["۳۵۰ میلیون"]), DOC, result("not_found"))
    assert score_records([row])["answer_completeness"]["value"] == 0.0
    assert score_records([row])["answer_correctness"]["value"] is None


def test_invalid_api_result_is_not_removed_from_denominator():
    row = evaluate_case(case("found", ["۳۵۰ میلیون"]), DOC, None, http_ok=False)
    score = score_records([row])
    assert score["invalid_responses"] == 1
    assert score["answer_completeness"]["value"] == 0.0


@pytest.mark.parametrize("url", ["https://localhost:8001", "http://example.org:8001",
                                "http://127.0.0.1:8001/other", "http://user@localhost:8001",
                                "http://localhost", "http://localhost:99999"])
def test_remote_or_malformed_endpoint_rejected(url):
    with pytest.raises(EvaluationInputError):
        validate_base_url(url)


def test_local_endpoint_accepted():
    assert validate_base_url("http://127.0.0.1:8001/") == "http://127.0.0.1:8001"


def test_tampered_fixture_is_rejected(tmp_path):
    data = load_fixture(FIXTURE)
    tampered = copy.deepcopy(data)
    tampered["cases"][0]["facts"] = ["fake-answer-injected"]
    path = tmp_path / "bad.json"
    import json
    path.write_text(json.dumps(tampered, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(EvaluationInputError):
        load_fixture(path)


def test_incorrect_source_paragraph_cannot_pass_grounding():
    text = "بودجه پروژه ۳۵۰ میلیون بود."
    payload = result("found", text, [text])
    payload["evidence"][0]["paragraph"] = 2
    row = evaluate_case(case("found", ["۳۵۰ میلیون"]), DOC, payload)
    assert row["source_grounded"] is False and row["complete_and_correct"] is False


def test_malformed_status_fails_closed_without_crashing():
    payload = result("found", "بودجه پروژه ۳۵۰ میلیون بود.", ["بودجه پروژه ۳۵۰ میلیون بود."])
    payload["status"] = ["found"]
    row = evaluate_case(case("found", ["۳۵۰ میلیون"]), DOC, payload)
    assert row["actual_status"] == "invalid_response"
