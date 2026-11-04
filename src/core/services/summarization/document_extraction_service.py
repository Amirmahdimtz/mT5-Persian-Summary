"""In-memory, HTTP-independent extraction of TXT, text PDFs, and DOCX files."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Literal
from io import BytesIO
from pathlib import Path
from zipfile import BadZipFile, LargeZipFile, ZipFile

from docx import Document
from docx.opc.exceptions import PackageNotFoundError
from docx.oxml.exceptions import InvalidXmlError
from docx.table import Table
from docx.text.paragraph import Paragraph
from lxml.etree import XMLSyntaxError
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from src.infrastructure.di.inject import inject


class DocumentExtractionError(ValueError):
    """Base class for invalid or unextractable document input."""


class UnsupportedDocumentTypeError(DocumentExtractionError):
    """The file extension is not supported."""


class EmptyDocumentError(DocumentExtractionError):
    """The input byte stream is empty."""


class InvalidDocumentError(DocumentExtractionError):
    """The document contains invalid input bytes or has an invalid signature."""


class InvalidTextEncodingError(InvalidDocumentError):
    """The TXT input cannot be decoded as UTF-8."""


class CorruptedDocumentError(InvalidDocumentError):
    """The supplied PDF or DOCX structure is corrupted."""


class PasswordProtectedPdfError(DocumentExtractionError):
    """Encrypted PDFs are not processed."""


class NoExtractableTextError(DocumentExtractionError):
    """No usable text was found (possibly an image-only document)."""


class DocumentLimitError(DocumentExtractionError):
    """The document exceeds an extraction-stage resource budget."""


class DocumentParsingError(RuntimeError):
    """The document parser failed for a reason other than known invalid input."""



@dataclass(frozen=True, slots=True)
class SourceLocation:
    """Parser-established location, never an inferred page/paragraph number."""

    document_type: Literal["txt", "pdf", "docx"]
    page: int | None = None
    paragraph: int | None = None
    section: str | None = None
    table: int | None = None
    row: int | None = None


@dataclass(frozen=True, slots=True)
class DocumentSegment:
    text: str
    source_location: SourceLocation
    document_order: int  # Zero-based across nonempty evidence windows.


@inject
class DocumentExtractionService:
    """Extract Unicode text without filesystem writes, model calls or HTTP types.

    Resource budgets are safeguards for untrusted in-memory inputs; Stage 6/7
    still need to enforce upload/body limits *before* reading the entire stream.
    """

    MAX_INPUT_BYTES = 20 * 1024 * 1024
    MAX_TEXT_CHARACTERS = 5_000_000
    MAX_PDF_PAGES = 500
    MAX_DOCX_MEMBERS = 2_000
    MAX_DOCX_PART_BYTES = 20 * 1024 * 1024
    MAX_DOCX_UNCOMPRESSED_BYTES = 80 * 1024 * 1024

    def extract(self, content: bytes, filename: str) -> str:
        """Return normalized Unicode content, selecting the parser by extension."""
        if not isinstance(filename, str) or not filename.strip():
            raise UnsupportedDocumentTypeError("filename must have a supported extension")
        suffix = Path(filename).suffix.lower()
        if suffix == ".txt":
            return self.extract_txt(content)
        if suffix == ".pdf":
            return self.extract_pdf(content)
        if suffix == ".docx":
            return self.extract_docx(content)
        raise UnsupportedDocumentTypeError("supported extensions are .txt, .pdf and .docx")

    MAX_SEGMENT_CHARACTERS = 1200
    SEGMENT_OVERLAP_CHARACTERS = 120
    MAX_SEGMENTS = 8192

    @classmethod
    def _append_segment_windows(
        cls, segments: list[DocumentSegment], value: str, location: SourceLocation
    ) -> None:
        """Create source-exact sentence excerpts, overlapping only long spans."""
        for sentence in re.split(r"(?<=[.!?؟])[ \t\n]+", value.strip()):
            source = sentence.strip()
            start = 0
            while start < len(source):
                end = min(start + cls.MAX_SEGMENT_CHARACTERS, len(source))
                if end < len(source):
                    # Prefer a whitespace boundary in the final half of a window.
                    boundary = max(
                        source.rfind(" ", start + cls.MAX_SEGMENT_CHARACTERS // 2, end),
                        source.rfind("\n", start + cls.MAX_SEGMENT_CHARACTERS // 2, end),
                    )
                    if boundary > start:
                        end = boundary + 1
                excerpt = source[start:end].strip()
                if excerpt:
                    if len(segments) >= cls.MAX_SEGMENTS:
                        raise DocumentLimitError("document exceeds the segment count limit")
                    segments.append(DocumentSegment(excerpt, location, len(segments)))
                if end == len(source):
                    break
                next_start = max(start + 1, end - cls.SEGMENT_OVERLAP_CHARACTERS)
                # The preceding window already contains this partial word.
                while next_start < end and not source[next_start - 1].isspace():
                    next_start += 1
                start = next_start

    def extract_segments(self, content: bytes, filename: str) -> tuple[DocumentSegment, ...]:
        """Extract bounded source evidence with truthful page/paragraph locations.

        Does not change extract(content, filename) -> str. PDF page numbers are
        one-based including blank pages; DOCX has no synthesized page numbers.
        """
        if not isinstance(filename, str) or not filename.strip():
            raise UnsupportedDocumentTypeError("filename must have a supported extension")
        suffix = Path(filename).suffix.lower()
        segments: list[DocumentSegment] = []
        if suffix == ".txt":
            text = self.extract_txt(content)
            if len(text) > self.MAX_TEXT_CHARACTERS:
                raise DocumentLimitError("extracted text exceeds the character limit")
            for index, paragraph in enumerate(re.split(r"\n[ \t]*\n+", text), start=1):
                if paragraph.strip():
                    self._append_segment_windows(
                        segments, paragraph, SourceLocation("txt", paragraph=index)
                    )
        elif suffix == ".pdf":
            for number, page_text in self._pdf_pages(content):
                self._append_segment_windows(
                    segments, page_text, SourceLocation("pdf", page=number)
                )
        elif suffix == ".docx":
            segments = self._docx_segments(content)
        else:
            raise UnsupportedDocumentTypeError("supported extensions are .txt, .pdf and .docx")
        if not segments:
            raise NoExtractableTextError("document contains no extractable text")
        return tuple(segments)

    def _docx_segments(self, content: bytes) -> list[DocumentSegment]:
        self._validate_bytes(content)
        try:
            self._check_docx_container(content)
            document = Document(BytesIO(content))
            segments: list[DocumentSegment] = []
            total_characters = 0
            paragraph_number = 0
            table_number = 0
            section: str | None = None
            for item in document.iter_inner_content():
                if isinstance(item, Paragraph):
                    paragraph_number += 1
                    text = item.text
                    total_characters += len(text)
                    if total_characters > self.MAX_TEXT_CHARACTERS:
                        raise DocumentLimitError("extracted text exceeds the character limit")
                    if item.style and item.style.name.startswith("Heading") and text.strip():
                        section = text.strip()[:160]
                    self._append_segment_windows(
                        segments, text, SourceLocation(
                            "docx", paragraph=paragraph_number, section=section
                        )
                    )
                else:
                    table_number += 1
                    seen_cells: set[object] = set()
                    for row_number, row in enumerate(item.rows, start=1):
                        cells: list[str] = []
                        for cell in row.cells:
                            if cell._tc in seen_cells:
                                continue
                            seen_cells.add(cell._tc)
                            cell_text = "\n".join(
                                text for part in cell.iter_inner_content()
                                if (text := self._content_text(part)).strip()
                            )
                            if cell_text.strip():
                                cells.append(cell_text)
                        text = "\t".join(cells)
                        total_characters += len(text)
                        if total_characters > self.MAX_TEXT_CHARACTERS:
                            raise DocumentLimitError("extracted text exceeds the character limit")
                        self._append_segment_windows(
                            segments, text, SourceLocation(
                                "docx", section=section, table=table_number, row=row_number
                            )
                        )
            return segments
        except DocumentExtractionError:
            raise
        except (BadZipFile, LargeZipFile, PackageNotFoundError, InvalidXmlError,
                XMLSyntaxError, KeyError, ValueError) as error:
            raise CorruptedDocumentError("DOCX is malformed or unreadable") from error
        except Exception as error:
            raise DocumentParsingError("DOCX text extraction failed") from error

    def extract_txt(self, content: bytes) -> str:
        self._validate_bytes(content)
        try:
            text = content.decode("utf-8-sig", errors="strict")
        except UnicodeDecodeError as error:
            raise InvalidTextEncodingError("TXT must be valid UTF-8 (optional BOM)") from error
        if any(ord(char) < 32 and char not in "\t\r\n" or char == "\x7f" for char in text):
            raise InvalidDocumentError("TXT contains invalid binary control characters")
        return self._normalize(text)

    def extract_pdf(self, content: bytes) -> str:
        return self._normalize(
            "\n\n".join(text for _, text in self._pdf_pages(content))
        )

    def _pdf_pages(self, content: bytes) -> list[tuple[int, str]]:
        """One-based actual page indexes; skip blank pages without renumbering."""
        self._validate_bytes(content)
        if b"%PDF-" not in content[:1024]:
            raise InvalidDocumentError("PDF signature is missing")
        try:
            reader = PdfReader(BytesIO(content), strict=True)
            if reader.is_encrypted:
                raise PasswordProtectedPdfError("encrypted PDFs are not supported")
            count = len(reader.pages)
            if count > self.MAX_PDF_PAGES:
                raise DocumentLimitError("PDF page count exceeds the extraction limit")
            pages: list[tuple[int, str]] = []
            total_characters = 0
            for number, page in enumerate(reader.pages, start=1):
                if "/Contents" not in page:
                    continue  # Valid blank pages need not have a content stream.
                # The existing conservative RTL restoration stays identical.
                text = page.extract_text(
                    extraction_mode="layout", layout_mode_strip_rotated=False
                ) or ""
                text = self._repair_reversed_pdf_years(self._restore_visual_rtl_text(text))
                total_characters += len(text)
                if total_characters > self.MAX_TEXT_CHARACTERS:
                    raise DocumentLimitError("extracted text exceeds the character limit")
                if text.strip():
                    pages.append((number, text))
            return pages
        except (PasswordProtectedPdfError, DocumentLimitError, NoExtractableTextError):
            raise
        except PdfReadError as error:
            raise CorruptedDocumentError("PDF is malformed or unreadable") from error
        except Exception as error:
            raise DocumentParsingError("PDF text extraction failed") from error

    def extract_docx(self, content: bytes) -> str:
        self._validate_bytes(content)
        try:
            self._check_docx_container(content)
            document = Document(BytesIO(content))
            parts: list[str] = []
            total_characters = 0
            for item in document.iter_inner_content():
                text = self._content_text(item)
                total_characters += len(text)
                if total_characters > self.MAX_TEXT_CHARACTERS:
                    raise DocumentLimitError("extracted text exceeds the character limit")
                if text.strip():
                    parts.append(text)
            return self._normalize("\n".join(parts))
        except DocumentExtractionError:
            raise
        except (BadZipFile, LargeZipFile, PackageNotFoundError, InvalidXmlError, XMLSyntaxError, KeyError, ValueError) as error:
            raise CorruptedDocumentError("DOCX is malformed or unreadable") from error
        except Exception as error:
            raise DocumentParsingError("DOCX text extraction failed") from error

    def _check_docx_container(self, content: bytes) -> None:
        try:
            with ZipFile(BytesIO(content)) as archive:
                members = archive.infolist()
                if len(members) > self.MAX_DOCX_MEMBERS:
                    raise DocumentLimitError("DOCX contains too many ZIP members")
                if not {"[Content_Types].xml", "word/document.xml"}.issubset(
                    {part.filename for part in members}
                ):
                    raise CorruptedDocumentError("DOCX required XML parts are missing")
                total = 0
                for member in members:
                    total += member.file_size
                    if member.file_size > self.MAX_DOCX_PART_BYTES:
                        raise DocumentLimitError("DOCX contains an oversized ZIP part")
                    if total > self.MAX_DOCX_UNCOMPRESSED_BYTES:
                        raise DocumentLimitError("DOCX expanded size exceeds the limit")
                    if member.flag_bits & 1:
                        raise CorruptedDocumentError("encrypted DOCX ZIP members are unsupported")
        except (BadZipFile, LargeZipFile) as error:
            raise CorruptedDocumentError("DOCX ZIP structure is invalid") from error

    # Frequent Persian function words and unambiguous vocabulary provide a
    # conservative signal of readable order without model inference.
    _PERSIAN_WORDS = frozenset(
        {
            "از", "است", "این", "آن", "با", "برای", "به", "تا", "در",
            "را", "شد", "شود", "که", "می", "نیز", "هم", "و", "یک",
            "اگر", "اما", "های", "ها", "متن", "فارسی", "سند", "نمونه",
            "سلام", "صفحه", "سال", "داده", "هوش", "مصنوعی",
        }
    )

    @staticmethod
    def _repair_reversed_pdf_years(text: str) -> str:
        """Correct clearly impossible reversed years after Persian month names.

        RTL PDF producers can reverse year digits while preserving the month.
        Never transform unrelated numbers, financial amounts or plausible years.
        """
        months = (
            "فروردین|اردیبهشت|خرداد|تیر|مرداد|شهریور|مهر|آبان|"
            "آذر|دی|بهمن|اسفند"
        )
        pattern = re.compile(rf"((?:{months})\s+)([۰-۹٠-٩0-9]{{4}})")

        def repair(match: re.Match[str]) -> str:
            digits = match.group(2)
            normalized = "".join(str(unicodedata.digit(char)) for char in digits)
            year, reversed_year = int(normalized), int(normalized[::-1])
            if (year > 2500 and
                    (1300 <= reversed_year <= 1499 or 1900 <= reversed_year <= 2099)):
                return match.group(1) + digits[::-1]
            return match.group(0)

        return pattern.sub(repair, text)

    @classmethod
    def _restore_visual_rtl_text(cls, text: str) -> str:
        """Repair clearly visual-order Persian PDF output without blind reversal.

        Some PDF producers store RTL glyphs in visual order. pypdf's layout
        mode exposes that visual order (e.g. 'یسراف نتم'), while other PDFs
        already return correct logical-order Unicode. Leave ambiguous pages
        unchanged rather than silently corrupt a correctly encoded PDF.
        """
        if not any(unicodedata.bidirectional(ch) in ("AL", "R") for ch in text):
            return text

        choices: list[tuple[str, str, int, int]] = []
        for line in text.split("\n"):
            tokens = line.split()
            rtl = sum(unicodedata.bidirectional(ch) in ("AL", "R") for ch in line)
            latin = sum(unicodedata.bidirectional(ch) == "L" for ch in line)
            candidate = (
                " ".join(cls._restore_visual_token(token) for token in reversed(tokens))
                if rtl and rtl >= latin
                else line
            )
            choices.append(
                (
                    line,
                    candidate,
                    cls._persian_word_score(line),
                    cls._persian_word_score(candidate),
                )
            )
        # A document can mix logical and visual-order lines. Honor the
        # per-line evidence first; use the page majority for ambiguous lines.
        visual_page = sum(new - old for _, _, old, new in choices) >= 2
        return "\n".join(
            candidate if new >= old + 2 or (visual_page and new >= old) else original
            for original, candidate, old, new in choices
        )

    @classmethod
    def _persian_word_score(cls, text: str) -> int:
        words = re.findall(r"[\u0600-\u06ff\u200c]+", text)
        return sum(word in cls._PERSIAN_WORDS for word in words)

    @staticmethod
    def _restore_visual_token(token: str) -> str:
        """Reverse RTL grapheme clusters, keeping standalone numeric/LTR tokens."""
        if not any(unicodedata.bidirectional(ch) in ("AL", "R") for ch in token):
            return token
        graphemes: list[str] = []
        for char in token:
            if unicodedata.combining(char) and graphemes:
                graphemes[-1] += char
            else:
                graphemes.append(char)
        return "".join(reversed(graphemes))

    @classmethod
    def _content_text(cls, item: Paragraph | Table) -> str:
        if isinstance(item, Paragraph):
            return item.text
        rows: list[str] = []
        seen_cells: set[object] = set()
        for row in item.rows:
            cells: list[str] = []
            for cell in row.cells:
                # Retain XML elements: id(cell._tc) can be reused for a later
                # cell when a transient lxml wrapper is garbage-collected.
                identity = cell._tc
                if identity in seen_cells:
                    continue
                seen_cells.add(identity)
                cell_parts = [cls._content_text(block) for block in cell.iter_inner_content()]
                cells.append("\n".join(value for value in cell_parts if value.strip()))
            if cells:
                rows.append("\t".join(cells))
        return "\n".join(rows)

    @classmethod
    def _validate_bytes(cls, content: bytes) -> None:
        if not isinstance(content, bytes):
            raise InvalidDocumentError("document content must be bytes")
        if not content:
            raise EmptyDocumentError("document bytes are empty")
        if len(content) > cls.MAX_INPUT_BYTES:
            raise DocumentLimitError("document input exceeds the byte limit")

    @staticmethod
    def _normalize(text: str) -> str:
        normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
        if not normalized:
            raise NoExtractableTextError("document contains no extractable text")
        return normalized
