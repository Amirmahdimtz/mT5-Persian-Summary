"""Shared, bounded upload validation for summarization and document-query APIs."""

from __future__ import annotations

from pathlib import PurePath

from fastapi import HTTPException, UploadFile

from src.core.services.summarization.document_extraction_service import DocumentExtractionService

MAX_FILE_BYTES = DocumentExtractionService.MAX_INPUT_BYTES
READ_CHUNK_BYTES = 64 * 1024
MAX_FILENAME_CHARACTERS = 255
SUPPORTED_MIME = {
    ".txt": "text/plain",
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def _http_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})


def validate_upload(upload: UploadFile) -> str:
    """Require an ordinary basename, known extension and matching declared MIME."""
    filename = upload.filename
    if (not isinstance(filename, str) or not filename
            or len(filename) > MAX_FILENAME_CHARACTERS
            or filename != filename.strip() or filename in (".", "..")
            or any(char in filename for char in "/\\")
            or any(ord(char) < 32 or ord(char) == 127 for char in filename)):
        raise _http_error(400, "InvalidFilename", "Filename must be a plain, safe basename.")
    try:
        filename.encode("utf-8", errors="strict")
    except UnicodeEncodeError:
        raise _http_error(400, "InvalidFilename", "Filename must be valid Unicode.") from None
    suffix = PurePath(filename).suffix.lower()
    if suffix not in SUPPORTED_MIME:
        raise _http_error(415, "UnsupportedDocumentTypeError", "Supported types: .txt, .pdf, .docx.")
    media_type = (upload.content_type or "").split(";", 1)[0].strip().lower()
    if media_type not in ("", "application/octet-stream", SUPPORTED_MIME[suffix]):
        raise _http_error(415, "UnsupportedMediaType", "File media type does not match extension.")
    return filename


async def read_upload_async(
    upload: UploadFile, available_bytes: int, *, max_file_bytes: int = MAX_FILE_BYTES,
) -> bytes:
    """Cap bytes as they arrive; never rely on Content-Length or upload.size."""
    allowed = min(max_file_bytes, available_bytes)
    if allowed < 1:
        raise _http_error(413, "AggregateUploadLimit", "Aggregate upload limit exceeded.")
    if upload.size is not None and upload.size > max_file_bytes:
        raise _http_error(413, "FileTooLarge", "File exceeds 20 MiB.")
    if upload.size is not None and upload.size > allowed:
        raise _http_error(413, "AggregateUploadLimit", "Aggregate upload limit exceeded.")

    buffer = bytearray()
    while True:
        chunk = await upload.read(min(READ_CHUNK_BYTES, allowed - len(buffer) + 1))
        if not chunk:
            break
        buffer.extend(chunk)
        if len(buffer) > allowed:
            code = "FileTooLarge" if allowed == max_file_bytes else "AggregateUploadLimit"
            raise _http_error(413, code, "Upload size limit exceeded.")
    if not buffer:
        raise _http_error(400, "EmptyDocumentError", "File must not be empty.")
    return bytes(buffer)
