"""Offline tests for real-project dataset preparation; no model loading."""
from __future__ import annotations

import copy
from pathlib import Path

import pytest

from benchmarks.project_document_dataset import git_blob_sha1, prepare
from benchmarks.quality_benchmark import BenchmarkInputError, validate_dataset


def sample(tmp_path: Path):
    content = "صورت جلسه آزمایشی در ۱۴ آبان نوشته شد.\n"
    path = tmp_path / "sample.md"
    path.write_text(content, encoding="utf-8")
    doc = {
        "id": "real_doc", "split": "dev", "category": "minutes",
        "source_path": "sample.md", "source_git_blob_sha1": git_blob_sha1(path.read_bytes()),
        "reference_summary": "جلسه در ۱۴ آبان ثبت شد.",
        "facts": [{"id": "date", "type": "date", "source_quote": "۱۴ آبان"}],
    }
    holdout = copy.deepcopy(doc)
    holdout.update(id="real_holdout", split="holdout")
    return {"version": 1, "cases": [doc, holdout]}


def test_project_dataset_validates_without_relicensing(tmp_path):
    manifest = sample(tmp_path)
    dataset = prepare(manifest, tmp_path)
    assert dataset["license"] == "PROJECT-REFERENCE-ONLY"
    assert dataset["cases"][0]["text"] == (tmp_path / "sample.md").read_bytes().decode("utf-8")
    assert len(validate_dataset(dataset)) == 2


def test_windows_crlf_checkout_matches_pinned_lf_git_blob(tmp_path):
    manifest = sample(tmp_path)
    path = tmp_path / "sample.md"
    lf_content = "صورت جلسه آزمایشی در ۱۴ آبان نوشته شد.\n"
    path.write_bytes(lf_content.encode("utf-8"))
    manifest["cases"][0]["source_git_blob_sha1"] = git_blob_sha1(path.read_bytes())
    manifest["cases"][1]["source_git_blob_sha1"] = git_blob_sha1(path.read_bytes())

    path.write_bytes(lf_content.replace("\n", "\r\n").encode("utf-8"))
    dataset = prepare(manifest, tmp_path)
    assert dataset["cases"][0]["text"] == lf_content
    assert dataset["cases"][1]["text"] == lf_content


def test_windows_crlf_checkout_still_rejects_changed_content(tmp_path):
    manifest = sample(tmp_path)
    path = tmp_path / "sample.md"
    lf_content = "صورت جلسه آزمایشی در ۱۴ آبان نوشته شد.\n"
    sha = git_blob_sha1(lf_content.encode("utf-8"))
    for case in manifest["cases"]:
        case["source_git_blob_sha1"] = sha
    path.write_bytes("صورت جلسه آزمایشی در ۱۵ آبان نوشته شد.\r\n".encode("utf-8"))
    with pytest.raises(BenchmarkInputError, match="Git blob SHA changed"):
        prepare(manifest, tmp_path)


def test_git_blob_integrity_detects_changes(tmp_path):
    manifest = sample(tmp_path)
    (tmp_path / "sample.md").write_text("متن جدید", encoding="utf-8")
    with pytest.raises(BenchmarkInputError, match="Git blob SHA changed"):
        prepare(manifest, tmp_path)


def test_rejects_path_escape(tmp_path):
    manifest = sample(tmp_path)
    manifest["cases"][0]["source_path"] = "../other.md"
    with pytest.raises((BenchmarkInputError, FileNotFoundError)):
        prepare(manifest, tmp_path)


def test_rejects_missing_quote(tmp_path):
    manifest = sample(tmp_path)
    manifest["cases"][0]["facts"][0]["source_quote"] = "ناموجود"
    with pytest.raises(BenchmarkInputError, match="source quote"):
        prepare(manifest, tmp_path)


def test_rejects_unapproved_license(tmp_path):
    manifest = sample(tmp_path)
    data = prepare(manifest, tmp_path)
    data["license"] = "mystery"
    with pytest.raises(BenchmarkInputError, match="license"):
        validate_dataset(data)


def test_rejects_bad_manifest_version(tmp_path):
    manifest = sample(tmp_path)
    manifest["version"] = 2
    with pytest.raises(BenchmarkInputError, match="manifest"):
        prepare(manifest, tmp_path)


def test_rejects_wrong_extension(tmp_path):
    manifest = sample(tmp_path)
    manifest["cases"][0]["source_path"] = "sample.pdf"
    with pytest.raises(BenchmarkInputError, match="Markdown"):
        prepare(manifest, tmp_path)


def test_rejects_absolute_path(tmp_path):
    manifest = sample(tmp_path)
    manifest["cases"][0]["source_path"] = str(tmp_path / "sample.md")
    with pytest.raises(BenchmarkInputError, match="repository-relative"):
        prepare(manifest, tmp_path)


def test_rejects_non_string_license(tmp_path):
    data = prepare(sample(tmp_path), tmp_path)
    data["license"] = []
    with pytest.raises(BenchmarkInputError, match="license"):
        validate_dataset(data)