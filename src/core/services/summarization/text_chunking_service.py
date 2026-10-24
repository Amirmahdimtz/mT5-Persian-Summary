"""Tokenizer-exact, lossless-after-whitespace-normalization Persian text chunks."""

from __future__ import annotations

import re

from src.infrastructure.di.inject import inject
from src.infrastructure.ml.mt5_model_provider import Mt5ModelProvider


class ChunkingInputError(ValueError):
    """The supplied text is empty or not a string."""


class ChunkingLimitError(ValueError):
    """Input exceeds the configured chunking work budget."""


@inject
class TextChunkingService:
    """Split at preferred prose boundaries, validating real mT5 token counts.

    Normalization folds CRLF/CR to LF, consecutive horizontal whitespace to
    one space, 3+ newlines to two, and strips document-edge whitespace. All
    characters in the normalized text are preserved in order across chunks.
    """

    MAX_TEXT_CHARACTERS = 200_000
    MAX_CHUNKS = 64
    _SENTENCE_END = re.compile(r"[.!?؟؛]+[ \t\n]+")
    _WORD_END = re.compile(r"\s+")

    def __init__(self, model_provider: Mt5ModelProvider) -> None:
        self._model_provider = model_provider

    @staticmethod
    def normalize(text: str) -> str:
        if not isinstance(text, str):
            raise ChunkingInputError("text must be a string")
        normalized = text.replace("\r\n", "\n").replace("\r", "\n")
        normalized = re.sub(r"[^\S\n]+", " ", normalized)
        normalized = re.sub(r"\n{3,}", "\n\n", normalized).strip()
        if not normalized:
            raise ChunkingInputError("text must contain non-whitespace characters")
        return normalized

    def fits(self, text: str) -> bool:
        """Whether provider can accept the exact text as one model input."""
        if not isinstance(text, str) or not text.strip():
            return False
        if len(text.strip()) > self._model_provider.max_input_characters:
            return False
        return self._model_provider.count_input_tokens(text) <= self._model_provider.max_input_tokens

    def chunk(self, text: str) -> list[str]:
        """Return nonempty, ordered chunks whose concatenation is normalized text.

        Reject unsupported work size and unrepresentable input explicitly;
        never silently truncate or drop a word/document tail.
        """
        normalized = self.normalize(text)
        if len(normalized) > self.MAX_TEXT_CHARACTERS:
            raise ChunkingLimitError("input exceeds chunking character budget")
        if self.fits(normalized):
            return [normalized]

        chunks: list[str] = []
        cursor = 0
        while cursor < len(normalized):
            if len(chunks) >= self.MAX_CHUNKS:
                raise ChunkingLimitError("input exceeds maximum chunk count")
            end = self._max_fitting_end(normalized, cursor)
            if end <= cursor:
                raise ChunkingLimitError("input contains a segment that cannot fit model limits")
            if end < len(normalized):
                preferred = self._preferred_boundary(normalized[cursor:end])
                if preferred is not None:
                    end = cursor + preferred
            chunk = normalized[cursor:end]
            if not chunk.strip():
                raise ChunkingLimitError("input contains an unrepresentable whitespace segment")
            if not self.fits(chunk):
                raise ChunkingLimitError("chunk exceeds model input budget")
            chunks.append(chunk)
            cursor = end

        if "".join(chunks) != normalized:
            raise ChunkingLimitError("chunk content coverage check failed")
        return chunks

    def _max_fitting_end(self, text: str, start: int) -> int:
        ceiling = min(len(text), start + self._model_provider.max_input_characters)
        if self.fits(text[start:ceiling]):
            return ceiling
        low, high = start + 1, ceiling
        best = start
        # Token counts are tested on exact candidate substrings with specials.
        # Even if token counts fluctuate at subword boundaries, every chosen
        # split is revalidated and no characters can be omitted.
        while low <= high:
            mid = (low + high) // 2
            if self.fits(text[start:mid]):
                best = mid
                low = mid + 1
            else:
                high = mid - 1
        return best

    @classmethod
    def _preferred_boundary(cls, candidate: str) -> int | None:
        # Avoid tiny chunks for early punctuation. Prefer paragraphs, then
        # newlines, sentences, then inter-word boundaries.
        cutoff = max(1, len(candidate) // 2)
        positions: list[int] = []
        pos = candidate.rfind("\n\n", cutoff)
        if pos >= 0:
            positions.append(pos + 2)
        pos = candidate.rfind("\n", cutoff)
        if pos >= 0:
            positions.append(pos + 1)
        if positions:
            return max(positions)
        for pattern in (cls._SENTENCE_END, cls._WORD_END):
            ends = [match.end() for match in pattern.finditer(candidate) if match.end() >= cutoff]
            if ends:
                return ends[-1]
        return None
