"""Fast tokenizer-contract tests; never download checkpoint weights."""

import pytest
from src.core.services.summarization.text_chunking_service import (
    ChunkingInputError, ChunkingLimitError, TextChunkingService,
)


class FakeTokenizerProvider:
    def __init__(self, tokens=21, chars=100, output=9):
        self.max_input_tokens = tokens
        self.max_input_characters = chars
        self.max_output_tokens = output
        self.calls = []

    def count_input_tokens(self, text):
        self.calls.append(text)
        # An explicit special EOS token must fit, in addition to all chars.
        return len(text.strip()) + 1


def service(tokens=21, chars=100):
    return TextChunkingService(FakeTokenizerProvider(tokens, chars))


@pytest.mark.parametrize('text', ['', ' \r\n\t  ', None, 42])
def test_empty_invalid_input(text):
    with pytest.raises(ChunkingInputError):
        service().chunk(text)


def test_short_and_exact_boundary():
    chunker = service(tokens=11)
    assert chunker.chunk('الف') == ['الف']
    assert chunker.chunk('abcdefghij') == ['abcdefghij']


def test_one_token_over_boundary_without_loss():
    chunker = service(tokens=11)
    text = 'abcdefghijk'
    chunks = chunker.chunk(text)
    assert len(chunks) == 2
    assert ''.join(chunks) == text
    assert all(chunker.fits(chunk) for chunk in chunks)


def test_large_persian_preserves_document_tail_and_order():
    chunker = service(tokens=41, chars=50)
    text = ('بخش اول. متن اصلی شامل اطلاعات فارسی است.\n\n' * 8) + 'پایان ویژه سند ۱۴۰۵'
    chunks = chunker.chunk(text)
    assert len(chunks) > 3
    assert ''.join(chunks) == text
    assert chunks[-1].endswith('پایان ویژه سند ۱۴۰۵')
    assert all(chunker.fits(chunk) for chunk in chunks)


def test_prefers_paragraph_boundary():
    text = 'شروع پاراگراف اول.\n\nشروع پاراگراف دوم. و ادامه مطالب.'
    chunks = service(tokens=37).chunk(text)
    assert len(chunks) >= 2
    assert chunks[0].endswith('\n\n')
    assert ''.join(chunks) == text


def test_one_huge_unpunctuated_paragraph_and_word():
    chunker = service(tokens=17)
    text = 'پیوستگی' * 20
    chunks = chunker.chunk(text)
    assert len(chunks) > 2
    assert ''.join(chunks) == text
    assert all(chunker.fits(chunk) for chunk in chunks)


def test_zwnj_persian_english_numerals_and_end():
    text = 'گزارش می\u200cشود ۱۲۳ 456. AI & ML مطرح است. پایان!'
    chunker = service(tokens=20)
    chunks = chunker.chunk(text)
    assert ''.join(chunks) == text
    assert 'می\u200cشود' in ''.join(chunks)
    assert 'AI & ML' in ''.join(chunks)
    assert chunks[-1].endswith('پایان!')


def test_whitespace_normalization_is_explicit_and_coverage_exact():
    raw = '  یک\r\n\r\n\r\n\t چند   واژه \r بعد  '
    normalized = 'یک\n\n چند واژه \n بعد'
    chunker = service(tokens=7)
    chunks = chunker.chunk(raw)
    assert ''.join(chunks) == normalized
    assert all(chunk.strip() for chunk in chunks)


def test_character_limit_even_if_tokens_fit():
    chunker = service(tokens=100, chars=5)
    chunks = chunker.chunk('abcdefghijkl')
    assert ''.join(chunks) == 'abcdefghijkl'
    assert all(len(c.strip()) <= 5 for c in chunks)


def test_special_tokens_count_at_limit():
    chunker = service(tokens=4, chars=20)
    assert chunker.fits('abc')
    assert not chunker.fits('abcd')
    assert ''.join(chunker.chunk('abcd')) == 'abcd'


def test_operational_limits_reject_instead_of_truncating():
    chunker = service(tokens=10)
    chunker.MAX_TEXT_CHARACTERS = 20
    with pytest.raises(ChunkingLimitError, match='character budget'):
        chunker.chunk('abcdefghij' * 3)
    chunker.MAX_TEXT_CHARACTERS = 500
    chunker.MAX_CHUNKS = 2
    with pytest.raises(ChunkingLimitError, match='chunk count'):
        chunker.chunk('abcdefghij' * 9)


def test_unrepresentable_single_character_budget_is_explicit():
    with pytest.raises(ChunkingLimitError, match='cannot fit'):
        service(tokens=1).chunk('abc')


def test_tokenizer_exception_propagates():
    chunker = service()
    def failed(_):
        raise RuntimeError('tokenizer unavailable')
    chunker._model_provider.count_input_tokens = failed
    with pytest.raises(RuntimeError, match='tokenizer unavailable'):
        chunker.chunk('متن')
