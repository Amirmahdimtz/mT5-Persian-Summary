"""HTTP request and response contracts for the summarization feature."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictStr, field_validator

from src.core.services.summarization.text_chunking_service import TextChunkingService


SummaryLength = Literal["short", "medium", "long"]


class TextSummarizationRequestDto(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: StrictStr = Field(
        min_length=1,
        max_length=TextChunkingService.MAX_TEXT_CHARACTERS,
        description="Nonempty source text; maximum 200,000 characters.",
    )
    summary_length: SummaryLength = "medium"

    @field_validator("text")
    @classmethod
    def nonblank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("text must contain non-whitespace characters")
        return value


class TextSummarizationResponseDto(BaseModel):
    summary: str
    summary_length: SummaryLength
    input_characters: int = Field(ge=0)
    output_characters: int = Field(ge=0)


class FileSummaryResponseDto(BaseModel):
    filename: str
    summary_length: SummaryLength
    success: bool
    summary: str | None = None
    input_characters: int | None = Field(default=None, ge=0)
    output_characters: int | None = Field(default=None, ge=0)
    error_code: str | None = None
    error_message: str | None = None


class MultiFileSummaryResponseDto(BaseModel):
    results: list[FileSummaryResponseDto]
    succeeded: int = Field(ge=0)
    failed: int = Field(ge=0)


class ErrorDetailDto(BaseModel):
    code: str
    message: str


class ErrorResponseDto(BaseModel):
    detail: ErrorDetailDto
