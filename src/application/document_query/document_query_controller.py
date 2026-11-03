"""Thin Document Query HTTP adapter, separate from the summarization routes."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile

from src.application.document_query.dtos.document_query_dto import (
    DocumentQueryResponseDto,
    SourceEvidenceDto,
)
from src.application.summarization.dtos.summarization_dto import ErrorResponseDto
from src.application.summarization.upload_limit_middleware import configured_upload_budget
from src.application.upload_validation import read_upload_async, validate_upload
from src.core.services.document_query.document_query_service import (
    DocumentQueryInputError,
    DocumentQueryResult,
    DocumentQueryService,
)
from src.core.services.summarization.document_extraction_service import (
    DocumentExtractionError,
    DocumentLimitError,
    DocumentParsingError,
    UnsupportedDocumentTypeError,
)
from src.core.services.summarization.document_retrieval_service import RetrievalInputError
from src.infrastructure.di.inject import inject
from src.infrastructure.utils.config_reader import ConfigReader


def _http_error(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


def _to_response(result: DocumentQueryResult) -> DocumentQueryResponseDto:
    evidence: list[SourceEvidenceDto] = []
    for entry in result.evidence:
        loc = entry.source_location
        location_type = "page" if loc.page is not None else (
            "table_row" if loc.table is not None else "paragraph"
        )
        evidence.append(SourceEvidenceDto(
            location_type=location_type,
            document_type=loc.document_type,
            page=loc.page,
            paragraph=loc.paragraph,
            section=loc.section,
            table=loc.table,
            row=loc.row,
            document_order=entry.document_order,
            text=entry.text,
        ))
    if result.status == "not_found" and (result.answer is not None or evidence):
        raise _http_error(500, "InvalidServiceResult", "Document query returned inconsistent evidence.")
    if result.status == "ambiguous" and (result.answer is not None or not evidence):
        raise _http_error(500, "InvalidServiceResult", "Document query returned inconsistent evidence.")
    if result.status == "found" and (
        not result.answer or not evidence
        or result.answer != "\n".join(item.text for item in evidence)
    ):
        raise _http_error(500, "InvalidServiceResult", "Document query returned ungrounded answer.")
    return DocumentQueryResponseDto(
        status=result.status,
        mode=result.mode,
        query=result.query,
        answer=result.answer,
        evidence=evidence,
    )


@inject
class DocumentQueryController:
    def __init__(
        self, document_query_service: DocumentQueryService, config_reader: ConfigReader
    ) -> None:
        self._service = document_query_service
        self._upload_budget = configured_upload_budget(config_reader)

    def api(self) -> APIRouter:
        router = APIRouter(tags=["Document Query"])
        errors = {code: {"model": ErrorResponseDto} for code in (400, 413, 415, 422, 500, 503)}

        @router.post(
            "/file", response_model=DocumentQueryResponseDto,
            summary="Answer a question or extract a topic-focused summary from one document",
            description=(
                "Multipart TXT, text PDF or DOCX plus required query. "
                "mode=answer (default) returns exact cited source text, not generated Q&A. "
                "mode=focused_summary returns bounded relevant original excerpts. "
                "summary_length is allowed only for focused_summary (default medium). "
                "All outputs are extractive; no mT5 generation or unsupported facts. "
                "Unresolved evidence conflicts are reported as ambiguous."
            ),
            responses=errors,
        )
        async def file_async(
            request: Request,
            file: Annotated[UploadFile, File(description="A single TXT/PDF/DOCX document")],
            query: Annotated[str, Form(min_length=1, max_length=512)],
            mode: Annotated[Literal["answer", "focused_summary"], Form()] = "answer",
            summary_length: Annotated[
                Literal["short", "medium", "long"] | None, Form()
            ] = None,
        ) -> DocumentQueryResponseDto:
            try:
                # FastAPI ignores extra multipart fields by default. Explicitly
                # reject them here, including repeated file/parameter names.
                form = await request.form()
                allowed = {"file", "query", "mode", "summary_length"}
                if (set(form) - allowed or
                        any(len(form.getlist(key)) != 1 for key in form)):
                    raise _http_error(422, "InvalidFormFields", "Unexpected or repeated form fields.")
                if mode == "answer" and summary_length is not None:
                    raise _http_error(
                        422, "InvalidSummaryLength", "summary_length requires focused_summary mode."
                    )
                filename = validate_upload(file)
                # Validate the query before reading the entire file; the core
                # retriever validates it again before structured extraction.
                self._service.validate_query(query)
                raw = await read_upload_async(file, self._upload_budget)
                result = await self._service.query_file_async(
                    raw, filename, query, mode=mode, summary_length=summary_length,
                )
                return _to_response(result)
            except UnsupportedDocumentTypeError as exc:
                raise _http_error(415, type(exc).__name__, "Unsupported document format.") from exc
            except DocumentLimitError as exc:
                raise _http_error(413, type(exc).__name__, "Processing resource limit exceeded.") from exc
            except (DocumentExtractionError, RetrievalInputError, DocumentQueryInputError) as exc:
                raise _http_error(422, type(exc).__name__, "Input cannot be processed.") from exc
            except DocumentParsingError as exc:
                raise _http_error(500, type(exc).__name__, "Document extraction failed.") from exc
            finally:
                await file.close()

        return router
