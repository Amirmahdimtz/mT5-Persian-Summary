"""Frozen Stage 9 Development source retrieval diagnostics (no mT5 load)."""

from __future__ import annotations

import argparse
from pathlib import Path

from benchmarks.quality_benchmark import (
    DATASET,
    BenchmarkInputError,
    dataset_hash,
    read_json,
    validate_dataset,
    write_json,
)
from src.core.services.summarization.document_extraction_service import DocumentExtractionService
from src.core.services.summarization.document_retrieval_service import DocumentRetrievalService


LABELS = Path(__file__).resolve().parent / "fixtures" / "stage11_retrieval_dev_v1.json"


def evaluate(dataset_path: Path = DATASET, labels_path: Path = LABELS) -> dict:
    dataset = read_json(dataset_path)
    cases = {item["id"]: item for item in validate_dataset(dataset) if item["split"] == "dev"}
    labels = read_json(labels_path)
    if labels.get("version") != 1 or labels.get("split") != "dev":
        raise BenchmarkInputError("Stage 11 labels must be the fixed Development split")
    queries = labels.get("queries")
    if not isinstance(queries, list) or not queries or len(queries) > 1000:
        raise BenchmarkInputError("Stage 11 labels must contain bounded queries")
    seen: set[str] = set()
    extractor = DocumentExtractionService()
    retriever = DocumentRetrievalService(extractor)
    indexed = {key: extractor.extract_segments(case["text"].encode("utf-8"), f"{key}.txt")
               for key, case in cases.items()}
    records: list[dict] = []
    for item in queries:
        if not isinstance(item, dict):
            raise BenchmarkInputError("invalid Stage 11 query record")
        ident, key, query, quote = (
            item.get("id"), item.get("case_id"), item.get("query"), item.get("expected_quote")
        )
        if (not isinstance(ident, str) or not ident.isidentifier() or ident in seen
                or key not in cases or not isinstance(query, str) or not query.strip()
                or not isinstance(quote, str) or quote not in cases[key]["text"]):
            raise BenchmarkInputError("invalid label id, case, query or evidence quote")
        seen.add(ident)
        result = retriever.retrieve_segments(indexed[key], query, top_k=3)
        hits = [hit.segment.text for hit in result.evidence]
        records.append({
            "id": ident, "case_id": key, "status": result.status,
            "recall_at_1": bool(hits and quote in hits[0]),
            "recall_at_3": any(quote in text for text in hits),
            "source_locations": [
                {"page": hit.segment.source_location.page,
                 "paragraph": hit.segment.source_location.paragraph,
                 "document_order": hit.segment.document_order}
                for hit in result.evidence
            ],
        })
    total = len(records)
    return {
        "version": 1,
        "source_split": "dev",
        "source_dataset_sha256": dataset_hash(dataset_path),
        "retrieval_labels_sha256": dataset_hash(labels_path),
        "evaluated_queries": total,
        "recall_at_1": sum(row["recall_at_1"] for row in records) / total,
        "recall_at_3": sum(row["recall_at_3"] for row in records) / total,
        "records": records,
        "limitation": "Retrieval only; no answer generation, human semantic audit or Production GO.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DATASET)
    parser.add_argument("--labels", type=Path, default=LABELS)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = evaluate(args.dataset, args.labels)
        write_json(args.output, report)  # non-destructive output
    except (OSError, ValueError) as error:
        parser.exit(2, f"Stage 11 retrieval benchmark failed: {type(error).__name__}: {error}\n")
    print(
        f"Stage 11 Development: {report['evaluated_queries']} labeled questions; "
        f"Recall@1={report['recall_at_1']:.3f}, Recall@3={report['recall_at_3']:.3f}; "
        f"report saved to {args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
