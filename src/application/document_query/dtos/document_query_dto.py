"""Strict HTTP response shapes for source-grounded document queries."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


QueryMode = Literal["answer", "focused_summary"]
SummaryLength = Literal["short", "medium", "long"]
QueryStatus = Literal["found", "not_found", "ambiguous"]


class SourceEvidenceDto(BaseModel):
    model_config = ConfigDict(extra="forbid")

    location_type: Literal["page", "paragraph", "table_row"]
    document_type: Literal["txt", "pdf", "docx"]
    page: int | None = Field(default=None, ge=1)
    paragraph: int | None = Field(default=None, ge=1)
    section: str | None = None
    table: int | None = Field(default=None, ge=1)
    row: int | None = Field(default=None, ge=1)
    document_order: int = Field(ge=0)
    text: str = Field(min_length=1, max_length=1200)


class DocumentQueryResponseDto(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: QueryStatus
    mode: QueryMode
    query: str = Field(min_length=1, max_length=512)
    answer: str | None = None
    evidence: list[SourceEvidenceDto]
