"""In-memory, HTTP-independent extraction of TXT, text PDFs, and DOCX files."""

from __future__ import annotations

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
            pages: list[str] = []
            total_characters = 0
            for page in reader.pages:
                if "/Contents" not in page:
                    continue  # Valid blank pages need not have a content stream.
                # Default plain extraction can reverse Persian letter order.
                # Include rotated text rather than silently dropping it.
                text = page.extract_text(
                    extraction_mode="layout", layout_mode_strip_rotated=False
                ) or ""
                total_characters += len(text)
                if total_characters > self.MAX_TEXT_CHARACTERS:
                    raise DocumentLimitError("extracted text exceeds the character limit")
                if text.strip():
                    pages.append(text)
            return self._normalize("\n\n".join(pages))
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

    @classmethod
    def _content_text(cls, item: Paragraph | Table) -> str:
        if isinstance(item, Paragraph):
            return item.text
        rows: list[str] = []
        seen_cells: set[int] = set()
        for row in item.rows:
            cells: list[str] = []
            for cell in row.cells:
                # Merged cells can occur several times in row.cells.
                identity = id(cell._tc)
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
