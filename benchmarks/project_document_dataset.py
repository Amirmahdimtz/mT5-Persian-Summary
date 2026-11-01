"""Materialize a local Stage 9 dataset from existing repository documents.

Repository documents are referenced by exact path and Git blob hash. Their
contents are NEVER committed or relicensed by this command. Generated JSON is
intended to be kept locally and is covered by .gitignore.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from benchmarks.quality_benchmark import (
    BenchmarkInputError,
    MAX_CASE_CHARS,
    read_json,
    validate_dataset,
    write_json,
)

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = Path(__file__).resolve().parent / "fixtures" / "real_project_documents_v1.json"


def git_blob_sha1(content: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(content)).encode("ascii") + b"\x00" + content).hexdigest()


def prepare(manifest: dict[str, Any], repo_root: Path) -> dict[str, Any]:
    """Validate pinned real-source references and materialize an in-memory dataset."""
    cases = manifest.get("cases")
    if manifest.get("version") != 1 or not isinstance(cases, list) or not cases:
        raise BenchmarkInputError("invalid project document manifest")
    root = repo_root.resolve(strict=True)
    ready: list[dict[str, Any]] = []
    for entry in cases:
        if not isinstance(entry, dict):
            raise BenchmarkInputError("manifest case must be an object")
        rel = entry.get("source_path")
        sha = entry.get("source_git_blob_sha1")
        if (not isinstance(rel, str) or not rel or not isinstance(sha, str)
                or len(sha) != 40 or any(c not in "0123456789abcdef" for c in sha)):
            raise BenchmarkInputError("invalid source path or Git blob SHA")
        relative = Path(rel)
        if relative.is_absolute() or relative.suffix.lower() != ".md":
            raise BenchmarkInputError("only repository-relative Markdown document paths are supported")
        path = (root / relative).resolve(strict=True)
        if not path.is_relative_to(root) or not path.is_file():
            raise BenchmarkInputError("source must be a regular file inside the repository")
        if path.stat().st_size > MAX_CASE_CHARS * 4:
            raise BenchmarkInputError("real document exceeds input byte budget")
        raw = path.read_bytes()
        if git_blob_sha1(raw) != sha:
            raise BenchmarkInputError(f"{rel}: Git blob SHA changed; re-approve the source and facts")
        try:
            source = raw.decode("utf-8-sig", errors="strict")
        except UnicodeError as exc:
            raise BenchmarkInputError("source is not UTF-8") from exc
        if len(source) > MAX_CASE_CHARS:
            raise BenchmarkInputError("real document exceeds input character budget")
        ready.append({**entry, "text": source})
    # These are existing repository documents, not CC0 benchmark test prose.
    dataset = {
        "version": 1,
        "license": "PROJECT-REFERENCE-ONLY",
        "origin": "Existing project-owned documents; reference-only local evaluation, no relicensing",
        "cases": ready,
    }
    validate_dataset(dataset)
    return dataset


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        dataset = prepare(read_json(args.manifest), args.repo_root)
        write_json(args.output, dataset)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.exit(2, f"Project benchmark preparation failed: {type(exc).__name__}: {exc}\n")
    print(f"Prepared {len(dataset['cases'])} pinned real project documents: {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())