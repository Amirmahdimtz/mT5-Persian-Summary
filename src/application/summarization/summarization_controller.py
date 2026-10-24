"""Thin HTTP entry points and bounded, disposable upload handling."""

from __future__ import annotations

from pathlib import PurePath
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from src.application.summarization.dtos.summarization_dto import (
    ErrorResponseDto,
    FileSummaryResponseDto,
    MultiFileSummaryResponseDto,
    SummaryLength,
    TextSummarizationRequestDto,
    TextSummarizationResponseDto,
)
from src.application.summarization.upload_limit_middleware import configured_upload_budget
from src.core.services.summarization.document_extraction_service import (
    CorruptedDocumentError,
    DocumentExtractionError,
    DocumentExtractionService,
    DocumentLimitError,
    DocumentParsingError,
    EmptyDocumentError,
    InvalidDocumentError,
    InvalidTextEncodingError,
    NoExtractableTextError,
    PasswordProtectedPdfError,
    UnsupportedDocumentTypeError,
)
from src.core.services.summarization.long_text_summarization_service import (
    SummarizationInputError,
    SummarizationLimitError,
    SummarizationNoProgressError,
)
from src.core.services.summarization.summarization_service import (
    DocumentInput,
    FileSummaryResult,
    SummarizationRequestError,
    SummarizationService,
)
from src.core.services.summarization.text_chunking_service import (
    ChunkingInputError,
    ChunkingLimitError,
)
from src.infrastructure.di.inject import inject
from src.infrastructure.ml.mt5_model_provider import (
    ModelInferenceError,
    ModelInputError,
    ModelLoadError,
)
from src.infrastructure.utils.config_reader import ConfigReader


_MAX_FILE_BYTES = DocumentExtractionService.MAX_INPUT_BYTES
_READ_CHUNK_BYTES = 64 * 1024
_MAX_FILENAME_CHARACTERS = 255
_SUPPORTED_MIME = {
    ".txt": "text/plain",
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
_SAFE_ERROR_CODES = frozenset({
    "DocumentExtractionError", "UnsupportedDocumentTypeError", "EmptyDocumentError",
    "InvalidDocumentError", "InvalidTextEncodingError", "CorruptedDocumentError",
    "PasswordProtectedPdfError", "NoExtractableTextError", "DocumentLimitError",
    "DocumentParsingError", "ChunkingInputError", "ChunkingLimitError",
    "SummarizationInputError", "SummarizationLimitError", "SummarizationNoProgressError",
    "ModelInputError", "ModelLoadError", "ModelInferenceError", "ModelOutputError",
    "SummaryOutputLimitError",
})


def _http_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})


def _raise_service_error(error: Exception) -> None:
    """Convert known operational failures without ever exposing exception text."""
    if isinstance(error, (DocumentLimitError, ChunkingLimitError, SummarizationLimitError)):
        status_code, message = 413, "Processing resource limit exceeded."
    elif isinstance(error, UnsupportedDocumentTypeError):
        status_code, message = 415, "Unsupported document format."
    elif isinstance(error, (DocumentExtractionError, SummarizationInputError, ChunkingInputError,
                            SummarizationRequestError, ModelInputError, SummarizationNoProgressError)):
        status_code, message = 422, "Input cannot be processed."
    elif isinstance(error, ModelLoadError):
        status_code, message = 503, "Summarization model is unavailable."
    elif isinstance(error, (ModelInferenceError, DocumentParsingError)):
        status_code, message = 500, "Summarization operation failed."
    else:
        raise error
    raise _http_error(status_code, type(error).__name__, message) from error


def _validate_upload(upload: UploadFile) -> str:
    filename = upload.filename
    if (not isinstance(filename, str) or not filename or len(filename) > _MAX_FILENAME_CHARACTERS
            or filename != filename.strip() or filename in (".", "..")
            or any(c in filename for c in "/\\")
            or any(ord(c) < 32 or ord(c) == 127 for c in filename)):
        raise _http_error(400, "InvalidFilename", "Filename must be a plain, safe basename.")
    try:
        filename.encode("utf-8", errors="strict")
    except UnicodeEncodeError:
        raise _http_error(400, "InvalidFilename", "Filename must be valid Unicode.") from None
    suffix = PurePath(filename).suffix.lower()
    if suffix not in _SUPPORTED_MIME:
        raise _http_error(415, "UnsupportedDocumentTypeError", "Supported types: .txt, .pdf, .docx.")
    media_type = (upload.content_type or "").split(";", 1)[0].strip().lower()
    if media_type not in ("", "application/octet-stream", _SUPPORTED_MIME[suffix]):
        raise _http_error(415, "UnsupportedMediaType", "File media type does not match extension.")
    return filename


async def _read_upload_async(upload: UploadFile, available_bytes: int) -> bytes:
    """Read no more than the smaller of per-file and aggregate remaining budget."""
    allowed = min(_MAX_FILE_BYTES, available_bytes)
    if allowed < 1:
        raise _http_error(413, "AggregateUploadLimit", "Aggregate upload limit exceeded.")
    if upload.size is not None and upload.size > _MAX_FILE_BYTES:
        raise _http_error(413, "FileTooLarge", "File exceeds 20 MiB.")
    if upload.size is not None and upload.size > allowed:
        raise _http_error(413, "AggregateUploadLimit", "Aggregate upload limit exceeded.")

    buffer = bytearray()
    while True:
        chunk = await upload.read(min(_READ_CHUNK_BYTES, allowed - len(buffer) + 1))
        if not chunk:
            break
        buffer.extend(chunk)
        if len(buffer) > allowed:
            code = "FileTooLarge" if allowed == _MAX_FILE_BYTES else "AggregateUploadLimit"
            raise _http_error(413, code, "Upload size limit exceeded.")
    if not buffer:
        raise _http_error(400, "EmptyDocumentError", "File must not be empty.")
    return bytes(buffer)


def _file_dto(result: FileSummaryResult) -> FileSummaryResponseDto:
    if result.success:
        if not isinstance(result.summary, str) or not result.summary.strip():
            raise _http_error(500, "InvalidServiceResult", "Summarization returned no usable text.")
        return FileSummaryResponseDto.model_validate(result, from_attributes=True)
    code = result.error_code if result.error_code in _SAFE_ERROR_CODES else "DocumentProcessingError"
    return FileSummaryResponseDto(
        filename=result.filename,
        summary_length=result.summary_length,
        success=False,
        error_code=code,
        error_message="Document could not be summarized; see error_code.",
    )


@inject
class SummarizationController:
    def __init__(self, summarization_service: SummarizationService, config_reader: ConfigReader) -> None:
        self._summarization_service = summarization_service
        self._max_total_bytes = configured_upload_budget(config_reader)

    def api(self) -> APIRouter:
        router = APIRouter(tags=["Summarization"])
        errors = {code: {"model": ErrorResponseDto} for code in (400, 413, 415, 422, 500, 503)}

        @router.post(
            "/text", response_model=TextSummarizationResponseDto,
            summary="Summarize Persian text",
            description="JSON text (1–200,000 characters); summary_length: short, medium or long (default medium).",
            responses=errors,
        )
        async def text_async(payload: TextSummarizationRequestDto) -> TextSummarizationResponseDto:
            try:
                result = await self._summarization_service.summarize_text_async(
                    payload.text, payload.summary_length
                )
            except (DocumentExtractionError, DocumentParsingError, SummarizationInputError,
                    SummarizationLimitError, SummarizationNoProgressError, ChunkingInputError,
                    ChunkingLimitError, ModelInputError, ModelLoadError, ModelInferenceError) as error:
                _raise_service_error(error)
            if not isinstance(result.summary, str) or not result.summary.strip():
                raise _http_error(500, "InvalidServiceResult", "Summarization returned no usable text.")
            return TextSummarizationResponseDto.model_validate(result, from_attributes=True)

        @router.post(
            "/file", response_model=FileSummaryResponseDto,
            summary="Summarize one TXT, text PDF or DOCX file",
            description="Multipart file field plus optional summary_length. 20 MiB/file, configurable aggregate budget (32 MiB default). "
                        "Files are read in 64 KiB chunks and never stored permanently by the application.",
            responses=errors,
        )
        async def file_async(
            file: Annotated[UploadFile, File(description="UTF-8 TXT, text PDF, or DOCX")],
            summary_length: Annotated[SummaryLength, Form()] = "medium",
        ) -> FileSummaryResponseDto:
            try:
                filename = _validate_upload(file)
                data = await _read_upload_async(file, self._max_total_bytes)
                try:
                    result = await self._summarization_service.summarize_file_async(
                        data, filename, summary_length
                    )
                except (DocumentExtractionError, DocumentParsingError, SummarizationInputError,
                        SummarizationLimitError, SummarizationNoProgressError, ChunkingInputError,
                        ChunkingLimitError, ModelInputError, ModelLoadError, ModelInferenceError) as error:
                    _raise_service_error(error)
                return _file_dto(result)
            finally:
                await file.close()

        @router.post(
            "/files", response_model=MultiFileSummaryResponseDto,
            summary="Summarize multiple files independently",
            description="Multipart `files` fields (1–32), optional summary_length. "
                        "20 MiB/file and configurable aggregate upload budget (32 MiB default); "
                        "HTTP 200 includes ordered success/failure results even if all documents fail. "
                        "Invalid collection/upload metadata is rejected at request level.",
            responses=errors,
        )
        async def files_async(
            files: Annotated[list[UploadFile], File(description="1–32 TXT/PDF/DOCX files")],
            summary_length: Annotated[SummaryLength, Form()] = "medium",
        ) -> MultiFileSummaryResponseDto:
            try:
                if not 1 <= len(files) <= SummarizationService.MAX_FILES:
                    raise _http_error(413, "InvalidFileCount", "Upload requires 1 to 32 files.")
                filenames = [_validate_upload(file) for file in files]
                remaining = self._max_total_bytes
                documents: list[DocumentInput] = []
                for upload, filename in zip(files, filenames):
                    content = await _read_upload_async(upload, remaining)
                    remaining -= len(content)
                    documents.append(DocumentInput(filename=filename, content=content))
                try:
                    result = await self._summarization_service.summarize_files_async(
                        documents, summary_length
                    )
                except (DocumentExtractionError, DocumentParsingError, SummarizationRequestError,
                        SummarizationInputError, SummarizationLimitError,
                        SummarizationNoProgressError, ChunkingInputError, ChunkingLimitError,
                        ModelInputError, ModelLoadError, ModelInferenceError) as error:
                    _raise_service_error(error)
                if len(result.results) != len(documents):
                    raise _http_error(500, "InvalidServiceResult", "Summarization returned incomplete results.")
                return MultiFileSummaryResponseDto(
                    results=[_file_dto(item) for item in result.results],
                    succeeded=result.succeeded,
                    failed=result.failed,
                )
            finally:
                for upload in files:
                    await upload.close()

        return router
