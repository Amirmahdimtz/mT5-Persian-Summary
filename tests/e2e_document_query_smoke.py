"""Opt-in live Stage 13 Document Query HTTP E2E; synthetic, no model inference.

Run from repository root:
  python tests/e2e_document_query_smoke.py --base-url http://127.0.0.1:8001
Also supports Docker's host port (often 8002). Does not evaluate holdout.
"""

from __future__ import annotations

import argparse
import statistics
import time

import httpx

from e2e_http_smoke import docx_bytes, pdf_bytes

SOURCE = "جلسه بعدی در تاریخ ۱۴ آبان ۱۴۰۵ برگزار می‌شود."
CONFLICT = "تاریخ جلسه بعدی ۱۴ آبان ۱۴۰۵ است.\n\nتاریخ جلسه بعدی ۱۵ آبان ۱۴۰۵ است."
QUERY = "تاریخ جلسه بعدی"
CANARY = "PRIVATE_STAGE13_CANARY_DO_NOT_LOG"


def _request(client: httpx.Client, name: str, content: bytes, mime: str, **fields: str) -> tuple[httpx.Response, float]:
    started = time.perf_counter()
    result = client.post(
        "/api/v1/document_query/file",
        files={"file": (name, content, mime)}, data=fields,
    )
    return result, (time.perf_counter() - started) * 1000


def _grounded(response: httpx.Response, original: str, *, mode: str, extension: str) -> None:
    if response.status_code != 200:
        raise AssertionError(f"{extension}/{mode}: unexpected HTTP {response.status_code}")
    payload = response.json()
    if payload.get("status") != "found" or payload.get("mode") != mode:
        raise AssertionError(f"{extension}/{mode}: expected found and correct mode")
    answer = payload.get("answer")
    evidence = payload.get("evidence")
    if not isinstance(answer, str) or not answer or not isinstance(evidence, list) or not evidence:
        raise AssertionError(f"{extension}/{mode}: empty or malformed answer/evidence")
    if answer != "\n".join(item["text"] for item in evidence):
        raise AssertionError(f"{extension}/{mode}: answer is not a verbatim concatenation of evidence")
    if not all(item["text"] in original for item in evidence):
        raise AssertionError(f"{extension}/{mode}: excerpt not found in the synthetic original source")
    if "۱۴ آبان ۱۴۰۵" not in answer:
        raise AssertionError(f"{extension}/{mode}: required date not preserved")
    for item in evidence:
        if item.get("document_type") != extension:
            raise AssertionError("document type misidentified")
        if extension == "pdf":
            if item.get("page") != 1 or item.get("paragraph") is not None:
                raise AssertionError("PDF page attribution is incorrect")
        else:
            if item.get("page") is not None or item.get("paragraph") != 1:
                raise AssertionError("TXT/DOCX paragraph attribution is incorrect")


def run(base_url: str, timeout: float) -> dict:
    """Exercise separate Document Query endpoint; never trigger mT5 generation."""
    observations: list[float] = []
    with httpx.Client(
        base_url=base_url.rstrip("/"), timeout=httpx.Timeout(timeout, connect=10.0),
        trust_env=False,
    ) as client:
        assert client.get("/api/v1/health").status_code == 200
        openapi = client.get("/openapi.json")
        assert openapi.status_code == 200
        routes = openapi.json()["paths"]
        for path in (
            "/api/v1/summarization/text",
            "/api/v1/summarization/file",
            "/api/v1/summarization/files",
            "/api/v1/document_query/file",
        ):
            if "post" not in routes[path]:
                raise AssertionError(f"missing POST route: {path}")

        samples = (
            ("txt", SOURCE.encode("utf-8"), "text/plain"),
            ("pdf", pdf_bytes(SOURCE), "application/pdf"),
            ("docx", docx_bytes(SOURCE), "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        )
        for extension, body, mime in samples:
            for mode in ("answer", "focused_summary"):
                fields = {"query": QUERY, "mode": mode}
                if mode == "focused_summary":
                    fields["summary_length"] = "short"
                response, milliseconds = _request(
                    client, f"stage13.{extension}", body, mime, **fields
                )
                observations.append(milliseconds)
                _grounded(response, SOURCE, mode=mode, extension=extension)
                print(f"PASS {extension}/{mode}: source location and exact evidence; {milliseconds:.1f} ms")

        empty, _ = _request(
            client, "none.txt", SOURCE.encode("utf-8"), "text/plain",
            query="واکسن کودکان",
        )
        if empty.status_code != 200 or empty.json().get("status") != "not_found":
            raise AssertionError("no-answer request did not abstain")
        if empty.json().get("answer") is not None or empty.json().get("evidence"):
            raise AssertionError("not_found unexpectedly includes a fabricated answer")
        print("PASS not_found: no answer or evidence")

        conflict, _ = _request(
            client, "conflicts.txt", CONFLICT.encode("utf-8"), "text/plain",
            query=QUERY,
        )
        result = conflict.json()
        if (conflict.status_code != 200 or result.get("status") != "ambiguous"
                or result.get("answer") is not None or len(result.get("evidence", [])) < 2):
            raise AssertionError("conflicting dates were not reported as ambiguous")
        print("PASS ambiguous: no invented resolution")

        error, _ = _request(
            client, "malformed.pdf", f"bad PDF {CANARY}".encode(), "application/pdf",
            query=QUERY,
        )
        if error.status_code != 422 or CANARY in error.text:
            raise AssertionError("malformed document returned wrong status or leaked raw input")
        print("PASS malformed input: sanitized HTTP 422")

        duplicate = client.post(
            "/api/v1/document_query/file",
            files=[
                ("file", ("duplicate.txt", SOURCE.encode(), "text/plain")),
                ("query", (None, "تاریخ جلسه")),
                ("query", (None, "تاریخ جلسه بعدی")),
            ],
        )
        if (duplicate.status_code != 422 or
                duplicate.json().get("detail", {}).get("code") != "InvalidFormFields"):
            raise AssertionError("duplicate multipart query fields were not rejected")
        print("PASS repeated multipart query: sanitized HTTP 422")

    return {
        "document_modes_verified": len(observations),
        "median_request_ms": round(statistics.median(observations), 2),
        "server_peak_rss_bytes": "NOT_MEASURED",
        "production_semantic_go": "NOT_APPROVED",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8001")
    parser.add_argument("--timeout", type=float, default=60.0)
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    metrics = run(args.base_url, args.timeout)
    print(f"PASS live Stage 13 HTTP E2E: {metrics}; synthetic evidence only")


if __name__ == "__main__":
    main()
