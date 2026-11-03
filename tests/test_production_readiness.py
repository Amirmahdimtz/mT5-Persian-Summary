"""Fail-closed production assessment and opt-in model-probe contract tests."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from benchmarks.production_release_gate import assess, main

_PROBE_PATH = Path(__file__).with_name("production_model_probe.py")
_spec = importlib.util.spec_from_file_location("production_model_probe_test_target", _PROBE_PATH)
assert _spec is not None and _spec.loader is not None
probe = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(probe)


def _development():
    from benchmarks.production_release_gate import (
        STAGE11_LABELS_SHA256, STAGE13_DEV_SHA256, STAGE9_DEV_SHA256,
    )
    return {
        "query_fixture_sha256": STAGE13_DEV_SHA256,
        "stage11_dev_labels_sha256": STAGE11_LABELS_SHA256,
        "stage9_dev_dataset_sha256": STAGE9_DEV_SHA256,
        "split": "dev", "stage11_queries": 15, "stage12_queries": 11,
        "stage10_frozen_semantic_quality_gate": "NOT_RETESTED",
        "production_semantic_quality_gate": "NOT_APPROVED",
        **{key: 1.0 for key in (
            "stage11_recall_at_1", "stage11_recall_at_3", "status_accuracy",
            "answer_exact_match", "evidence_support_rate", "no_answer_accuracy",
            "ambiguous_detection", "focused_coverage",
        )},
        "records": [{"id": f"case_{n}", "status_match": True} for n in range(11)],
    }


def _model():
    return {
        "status": "STRUCTURAL_PASS", "model_inference_exercised": True,
        "container_image_id": "sha256:" + "a" * 64,
        "dependency_snapshot": {"status": "MATCH", "pin_count": 48, "mismatch_names": []},
        "observations": [
            {"phase": "first_observed", "http_status": 200,
             "summary_characters": 20, "elapsed_ms": 3000.0},
            {"phase": "warm_repeat", "http_status": 200,
             "summary_characters": 20, "elapsed_ms": 400.0},
        ],
        "memory_after": {"current_bytes": 42, "peak_bytes": 100, "limit_bytes": 1024},
    }


def _review():
    return {
        "schema_version": 1, "review_scope": "authorized_real_persian_documents",
        "documents_reviewed": 30, "labeled_questions": 100,
        "independent_reviewer_ids": ["reviewer_a", "reviewer_b"],
        "independent_review_approved": True,
        "security_review_approved": True,
        "review_evidence_sha256": "a" * 64,
        "representative_retrieval_recall_at_3": 0.91,
        "stage10_frozen_development_gates": {
            "synthetic_medium_fact_total": 19,
            "synthetic_medium_facts_covered": 8,
            "critical_direction_inversions": 0,
            "synthetic_medium_fact_distortions": 0,
            "synthetic_unsupported_claim_rate": 0.12,
            "distinct_short_long_case_count": 3,
            "real_project_medium_fact_total": 6,
            "real_project_medium_facts_covered": 3,
            "critical_fabricated_facts": 0,
            "architecture_duplicate_fourgram_fraction": 0.0,
        },
    }


def test_missing_evidence_is_no_go():
    report = assess(None, None, None)
    assert report["decision"] == "NO_GO"
    assert report["production_go"] is False
    assert "independent_real_document_review" in report["blocked_checks"]


def test_complete_attestations_never_auto_approve():
    report = assess(_development(), _model(), _review(),
                    review_evidence_sha256="a" * 64)
    assert report["decision"] == "MANUAL_SIGNOFF_REQUIRED"
    assert report["production_go"] is False
    assert report["blocked_checks"] == []


def test_public_endpoint_always_blocks_without_security_gateway():
    report = assess(_development(), _model(), _review(),
                    review_evidence_sha256="a" * 64, visibility="public")
    assert report["decision"] == "NO_GO"
    assert "private_only_deployment" in report["blocked_checks"]


@pytest.mark.parametrize("mutation", [
    lambda m: m["records"][0].__setitem__("id", []),
    lambda m: m["records"][0].__setitem__("status_match", False),
    lambda m: m.__setitem__("split", "holdout"),
    lambda m: m.__setitem__("stage9_dev_dataset_sha256", "fake"),
    lambda m: m.__setitem__("answer_exact_match", True),
])
def test_invalid_development_report_blocks_without_crashing(mutation):
    metrics = _development()
    mutation(metrics)
    assert assess(metrics, _model(), _review(), review_evidence_sha256="a" * 64)["decision"] == "NO_GO"


def test_unmeasured_memory_blocks_release_gate():
    model = _model()
    model["memory_after"] = None
    assert assess(_development(), model, _review(),
                  review_evidence_sha256="a" * 64)["decision"] == "NO_GO"


def test_frozen_quality_gate_does_not_accept_below_threshold():
    review = _review()
    review["stage10_frozen_development_gates"]["real_project_medium_facts_covered"] = 2
    assert assess(_development(), _model(), review,
                  review_evidence_sha256="a" * 64)["decision"] == "NO_GO"


def test_false_critical_inversion_count_is_not_integer_zero():
    review = _review()
    review["stage10_frozen_development_gates"]["critical_direction_inversions"] = False
    assert assess(_development(), _model(), review,
                  review_evidence_sha256="a" * 64)["decision"] == "NO_GO"


def test_report_non_overwrite_and_cli_exit_is_not_success(tmp_path):
    target = tmp_path / "local_production_gate.json"
    assert main(["--output", str(target)]) == 2
    contents = target.read_bytes()
    assert json.loads(contents)["production_go"] is False
    with pytest.raises(SystemExit) as error:
        main(["--output", str(target)])
    assert error.value.code == 2
    assert target.read_bytes() == contents


@pytest.mark.parametrize("url", [
    "http://example.com:8000", "https://localhost:8000",
    "http://127.0.0.1", "http://localhost:8000/private",
    "http://127.0.0.1:99999", "http://alice@localhost:8000",
])
def test_model_probe_rejects_non_loopback_or_malformed_urls(url):
    with pytest.raises(ValueError):
        probe._local_url(url)


def test_model_probe_cgroup_reader_can_report_absent_metrics(monkeypatch):
    monkeypatch.setattr(probe, "_docker_value", lambda *_: None)
    assert probe._cgroup_memory("mt5-prod-probe") is None


def test_model_probe_is_bounded_and_uses_no_model_when_health_is_down(monkeypatch):
    monkeypatch.setattr(probe, "_cgroup_memory", lambda *_: None)
    monkeypatch.setattr(probe, "_docker_value", lambda *_: None)
    class FakeClient:
        def __init__(self, **_): pass
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def get(self, _):
            class Health: status_code = 503
            return Health()
    monkeypatch.setattr(probe.httpx, "Client", FakeClient)
    result = probe.run("http://127.0.0.1:8003", "mt5-prod-probe", 30, 2)
    assert result["status"] == "BLOCKED"
    assert result["observations"] == []
    assert result["model_inference_exercised"] is False


def test_docker_constraints_are_explicit_and_docker_context_includes_them():
    root = Path(__file__).resolve().parents[1]
    spec = "constraints/docker-linux-cpu-2026-11.txt"
    constraints = (root / spec).read_text(encoding="utf-8")
    pins = [line for line in constraints.splitlines() if line and not line.startswith("#")]
    assert len(pins) == 48
    assert all(line.count("==") == 1 for line in pins)
    assert len({line.split("==", 1)[0].casefold() for line in pins}) == len(pins)
    for dependency in ("torch==2.15.0+cpu", "transformers==4.57.6",
                       "pypdf==6.21.4", "python-docx==1.2.0"):
        assert dependency in pins
    dockerfile = (root / "Dockerfile").read_text(encoding="utf-8")
    assert f"COPY {spec}" in dockerfile
    assert dockerfile.count(f"--constraint {spec}") == 2
    dockerignore = (root / ".dockerignore").read_text(encoding="utf-8")
    assert f"!{spec}" in dockerignore


def test_ghcr_preview_publish_is_opt_in_only():
    import yaml
    root = Path(__file__).resolve().parents[1]
    content = (root / ".github/workflows/docker-image.yml").read_text(encoding="utf-8")
    workflow = yaml.load(content, Loader=yaml.BaseLoader)
    assert workflow["on"]["workflow_dispatch"]["inputs"]["publish_preview"]["default"] == "false"
    steps = workflow["jobs"]["build-and-publish"]["steps"]
    gated = [step for step in steps if step["name"] in (
        "Authenticate to GHCR", "Publish validated image")]
    assert len(gated) == 2
    assert all(step.get("if") == "inputs.publish_preview == true" for step in gated)


def test_dependency_snapshot_detects_changed_versions_without_exposing_content(monkeypatch):
    lock = Path(__file__).resolve().parents[1] / "constraints/docker-linux-cpu-2026-11.txt"
    pins = [line for line in lock.read_text(encoding="utf-8").splitlines()
            if line and not line.startswith("#")]
    monkeypatch.setattr(probe, "_docker_value", lambda *_: "\n".join(pins))
    report = probe._dependency_snapshot("mt5-prod-probe")
    assert report["status"] == "MATCH"
    assert report["pin_count"] == 48
    monkeypatch.setattr(probe, "_docker_value", lambda *_: "fastapi==0.001")
    mismatched = probe._dependency_snapshot("mt5-prod-probe")
    assert mismatched["status"] == "MISMATCH"
    assert "fastapi" in mismatched["mismatch_names"]


def test_model_report_without_audited_snapshot_cannot_unlock_gate():
    model = _model()
    model["dependency_snapshot"]["status"] = "NOT_MEASURED"
    assert assess(_development(), model, _review(),
                  review_evidence_sha256="a" * 64)["decision"] == "NO_GO"
