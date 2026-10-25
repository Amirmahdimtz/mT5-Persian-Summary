"""Opt-in real HTTP/real mT5 smoke against an already-running service.

Run explicitly (never imported by normal pytest):
  python tests/e2e_http_smoke.py --base-url http://127.0.0.1:8001
Repeat with port 8000 for Docker. This script creates only synthetic inputs.
"""

from __future__ import annotations

import argparse
from io import BytesIO

import httpx
from docx import Document
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

BASE_TEXT = (
    "سازمان هواشناسی اعلام کرد که بارش باران در روزهای آینده در شمال کشور "
    "افزایش می‌یابد. کارشناسان توصیه کردند رانندگان پیش از سفر شرایط جاده‌ها "
    "را بررسی کنند و به هشدارهای هواشناسی توجه داشته باشند."
)


def pdf_bytes(text: str) -> bytes:
    """Create a tiny text-layer PDF with a deterministic Persian ToUnicode map."""
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    letters = list(dict.fromkeys(text))
    if len(letters) >= 256:
        raise ValueError("The synthetic PDF supports fewer than 256 distinct characters")
    mapping = {char: index + 1 for index, char in enumerate(letters)}
    chars = "\n".join(f"<{index:02X}> <{ord(char):04X}>" for char, index in mapping.items())
    cmap = (
        "/CIDInit /ProcSet findresource begin\n12 dict begin\nbegincmap\n"
        "/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def\n"
        "/CMapName /Adobe-Identity-UCS def\n/CMapType 2 def\n"
        "1 begincodespacerange\n<00> <FF>\nendcodespacerange\n"
        f"{len(mapping)} beginbfchar\n{chars}\nendbfchar\n"
        "endcmap\nCMapName currentdict /CMap defineresource pop\nend\nend"
    ).encode("ascii")
    unicode_map = DecodedStreamObject()
    unicode_map.set_data(cmap)
    font = DictionaryObject({
        NameObject("/Type"): NameObject("/Font"),
        NameObject("/Subtype"): NameObject("/Type1"),
        NameObject("/BaseFont"): NameObject("/Helvetica"),
        NameObject("/Encoding"): NameObject("/WinAnsiEncoding"),
        NameObject("/ToUnicode"): writer._add_object(unicode_map),
    })
    page[NameObject("/Resources")] = DictionaryObject({
        NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})
    })
    content = DecodedStreamObject()
    encoded_text = "".join(f"{mapping[char]:02X}" for char in text)
    content.set_data(f"BT /F1 12 Tf 50 700 Td <{encoded_text}> Tj ET".encode("ascii"))
    page[NameObject("/Contents")] = writer._add_object(content)
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def docx_bytes(text: str) -> bytes:
    document = Document()
    document.add_paragraph(text)
    output = BytesIO()
    document.save(output)
    return output.getvalue()


def verify_success(response: httpx.Response, *, context: str) -> dict:
    if response.status_code != 200:
        raise AssertionError(f"{context}: HTTP {response.status_code}, expected 200")
    result = response.json()
    if not isinstance(result, dict):
        raise AssertionError(f"{context}: response is not a JSON object")
    return result


def verify_summary(value: dict, *, context: str) -> None:
    if value.get("success", True) is not True:
        raise AssertionError(f"{context}: unsuccessful result: {value.get('error_code')}")
    if not isinstance(value.get("summary"), str) or not value["summary"].strip():
        raise AssertionError(f"{context}: empty or invalid summary")
    print(f"PASS {context}: summary_chars={len(value['summary'])}")


def run(base_url: str, timeout: float, large_upload: bool) -> None:
    with httpx.Client(base_url=base_url.rstrip("/"), timeout=httpx.Timeout(timeout, connect=15.0), trust_env=False) as client:
        health = verify_success(client.get("/api/v1/health"), context="health")
        assert health == {"status": "ok"}
        print("PASS liveness (model readiness is NOT implied)")
        assert client.get("/docs").status_code == 200
        openapi = verify_success(client.get("/openapi.json"), context="openapi")
        for route in ("text", "file", "files"):
            assert "post" in openapi["paths"][f"/api/v1/summarization/{route}"]
        print("PASS Swagger and three OpenAPI operations")

        for length in ("short", "medium", "long"):
            result = verify_success(client.post("/api/v1/summarization/text", json={
                "text": BASE_TEXT, "summary_length": length,
            }), context=f"text/{length}")
            assert result["summary_length"] == length
            assert result["input_characters"] == len(BASE_TEXT)
            verify_summary(result, context=f"text/{length}")

        documents = [
            ("sample.txt", BASE_TEXT.encode("utf-8"), "text/plain"),
            ("sample.pdf", pdf_bytes(BASE_TEXT), "application/pdf"),
            ("sample.docx", docx_bytes(BASE_TEXT), "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        ]
        for name, data, mime in documents:
            result = verify_success(client.post("/api/v1/summarization/file",
                files={"file": (name, data, mime)}, data={"summary_length": "medium"}), context=name)
            assert result["filename"] == name
            verify_summary(result, context=name)

        batch = verify_success(client.post("/api/v1/summarization/files",
            files=[("files", (name, data, mime)) for name, data, mime in documents],
            data={"summary_length": "medium"}), context="multi-file")
        assert batch["succeeded"] == 3 and batch["failed"] == 0
        assert [result["filename"] for result in batch["results"]] == [item[0] for item in documents]
        for result in batch["results"]:
            verify_summary(result, context=f"batch/{result['filename']}")

        marker = "PRIVATE_E2E_SECRET"
        invalid = client.post("/api/v1/summarization/file", files={
            "file": ("corrupt.pdf", f"not a pdf {marker}".encode(), "application/pdf")})
        assert invalid.status_code == 422, invalid.status_code
        assert marker not in invalid.text
        assert invalid.json()["detail"]["code"] == "InvalidDocumentError"
        print("PASS malformed PDF -> sanitized 422")

        bad_name = client.post("/api/v1/summarization/file", files={
            "file": ("../unsafe.txt", BASE_TEXT.encode(), "text/plain")})
        assert bad_name.status_code == 400
        print("PASS unsafe filename -> 400")

        bad_text = client.post("/api/v1/summarization/text", json={
            "text": BASE_TEXT, "summary_length": "invalid"})
        assert bad_text.status_code == 422
        print("PASS invalid summary length -> 422")

        if large_upload:
            oversized = client.post("/api/v1/summarization/file", files={
                "file": ("oversize.txt", b"a" * (20 * 1024 * 1024 + 1), "text/plain")})
            assert oversized.status_code == 413, oversized.status_code
            print("PASS file above 20 MiB -> 413")
        else:
            print("NOT RUN large-upload HTTP 413 (pass --large-upload to enable)")

        print("PASS live HTTP E2E smoke; this is not a factual-quality benchmark")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8001")
    parser.add_argument("--timeout", type=float, default=900.0,
                        help="Per-request timeout in seconds; does not enforce server inference timeout")
    parser.add_argument("--large-upload", action="store_true",
                        help="Also send a synthetic >20 MiB upload to verify HTTP 413")
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    run(args.base_url, args.timeout, args.large_upload)


if __name__ == "__main__":
    main()
