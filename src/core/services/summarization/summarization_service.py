"""HTTP-independent orchestration for Persian text and document summaries."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass

from src.core.services.summarization.document_extraction_service import (
    DocumentExtractionError,
    DocumentExtractionService,
    DocumentParsingError,
)
from src.core.services.summarization.long_text_summarization_service import (
    LongTextSummarizationService,
    SummarizationInputError,
    SummarizationLimitError,
    SummarizationNoProgressError,
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


class SummarizationRequestError(ValueError):
    """The multi-file collection is invalid, independent of any document."""


@dataclass(frozen=True, slots=True)
class DocumentInput:
    """An in-memory document; input position is retained even for duplicate names."""

    filename: str
    content: bytes


@dataclass(frozen=True, slots=True)
class TextSummaryResult:
    summary: str
    summary_length: str
    input_characters: int
    output_characters: int


@dataclass(frozen=True, slots=True)
class FileSummaryResult:
    filename: str
    summary_length: str
    success: bool
    summary: str | None = None
    input_characters: int | None = None
    output_characters: int | None = None
    error_code: str | None = None
    error_message: str | None = None


@dataclass(frozen=True, slots=True)
class MultiFileSummaryResult:
    results: tuple[FileSummaryResult, ...]

    @property
    def succeeded(self) -> int:
        return sum(item.success for item in self.results)

    @property
    def failed(self) -> int:
        return len(self.results) - self.succeeded


# Only known operational failures are handled per document. Programming errors,
# system-level failures and cancellation remain visible to the caller.
_FILE_ERRORS = (
    DocumentExtractionError,
    DocumentParsingError,
    SummarizationInputError,
    SummarizationLimitError,
    SummarizationNoProgressError,
    ChunkingInputError,
    ChunkingLimitError,
    ModelInputError,
    ModelLoadError,
    ModelInferenceError,
)


@inject
class SummarizationService:
    """Orchestrate existing services without tokenizing or loading model weights.

    Files are processed sequentially, bounding in-flight extraction and inference
    to one file per request. The model provider serializes inference globally
    within its process. Callers must enforce upload size limits while reading.
    """

    MAX_FILES = 32
    _LENGTHS = ("short", "medium", "long")

    def __init__(
        self,
        document_extraction_service: DocumentExtractionService,
        long_text_summarization_service: LongTextSummarizationService,
    ) -> None:
        self._extractor = document_extraction_service
        self._long_text_service = long_text_summarization_service

    @classmethod
    def _validate_length(cls, summary_length: str) -> None:
        if not isinstance(summary_length, str) or summary_length not in cls._LENGTHS:
            raise SummarizationInputError("summary_length must be short, medium or long")

    async def summarize_text_async(
        self, text: str, summary_length: str = "medium"
    ) -> TextSummaryResult:
        self._validate_length(summary_length)
        if not isinstance(text, str) or not text.strip():
            raise SummarizationInputError("text must contain valid nonempty content")
        summary = await self._long_text_service.summarize_async(text, summary_length)
        if not isinstance(summary, str) or not summary.strip():
            raise ModelInferenceError("summarization returned no usable text")
        summary = summary.strip()
        return TextSummaryResult(
            summary=summary,
            summary_length=summary_length,
            input_characters=len(text),
            output_characters=len(summary),
        )

    async def summarize_file_async(
        self, content: bytes, filename: str, summary_length: str = "medium"
    ) -> FileSummaryResult:
        self._validate_length(summary_length)
        # Stage 3's synchronous parsers may be CPU intensive: never parse on
        # the ASGI event-loop thread. No disk materialization is performed.
        extracted = await asyncio.to_thread(self._extractor.extract, content, filename)
        result = await self.summarize_text_async(extracted, summary_length)
        return FileSummaryResult(
            filename=filename,
            summary_length=summary_length,
            success=True,
            summary=result.summary,
            input_characters=result.input_characters,
            output_characters=result.output_characters,
        )

    async def summarize_files_async(
        self, files: Sequence[DocumentInput], summary_length: str = "medium"
    ) -> MultiFileSummaryResult:
        self._validate_length(summary_length)
        if (
            not isinstance(files, Sequence)
            or isinstance(files, (str, bytes, bytearray))
            or not 1 <= len(files) <= self.MAX_FILES
        ):
            raise SummarizationRequestError(
                f"files must contain 1 to {self.MAX_FILES} DocumentInput items"
            )
        items = tuple(files)  # Snapshot mutable caller collections across awaits.
        if len(items) > self.MAX_FILES or any(not isinstance(item, DocumentInput) for item in items):
            raise SummarizationRequestError("files must contain DocumentInput items")

        results: list[FileSummaryResult] = []
        for item in items:
            try:
                result = await self.summarize_file_async(
                    item.content, item.filename, summary_length
                )
            except _FILE_ERRORS as error:
                # Never echo exception messages: backend/parser exceptions may
                # chain input-dependent details. Codes retain diagnostic value.
                results.append(
                    FileSummaryResult(
                        filename=item.filename if isinstance(item.filename, str) else "",
                        summary_length=summary_length,
                        success=False,
                        error_code=type(error).__name__,
                        error_message="Document could not be summarized; see error_code.",
                    )
                )
            else:
                results.append(result)
        return MultiFileSummaryResult(results=tuple(results))
