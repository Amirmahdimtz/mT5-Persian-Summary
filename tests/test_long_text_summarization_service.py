"""Mock-only hierarchical summarization tests without weights or network."""

import asyncio
import time
import pytest

from src.core.services.summarization.long_text_summarization_service import (
    LongTextSummarizationService, SummarizationInputError,
    SummarizationLimitError, SummarizationNoProgressError, SummaryOutputLimitError,
)
from src.core.services.summarization.text_chunking_service import TextChunkingService
from src.infrastructure.ml.mt5_model_provider import ModelOutputError


class FakeProvider:
    max_input_tokens = 21
    max_input_characters = 60
    max_output_tokens = 9

    def __init__(self, mode='shorten'):
        self.mode = mode
        self.calls = []

    def count_input_tokens(self, text):
        return len(text.strip()) + 1

    async def summarize_async(self, text, *, max_output_tokens=None):
        self.calls.append((text, max_output_tokens))
        if self.mode == 'error':
            raise RuntimeError('model inference failed')
        if self.mode == 'empty':
            return ' '
        if self.mode == 'unchanged':
            return text
        if self.mode == 'huge':
            return 'z' * 50
        return text[:max_output_tokens - 1].strip() or 'خ'


def service(provider=None):
    provider = provider or FakeProvider()
    return LongTextSummarizationService(TextChunkingService(provider), provider), provider


def run(coro):
    return asyncio.run(coro)


@pytest.mark.parametrize('level,limit', [('short',3),('medium',6),('long',9)])
def test_direct_short_path_length_mapping(level, limit):
    svc, fake = service()
    result = run(svc.summarize_async('متن فارسی', level))
    assert result
    assert fake.calls == [('متن فارسی', limit)]
    assert fake.count_input_tokens(result) <= limit


def test_default_length_is_medium_and_backward_compatible_service_call():
    svc, fake = service()
    assert run(svc.summarize_async('متن'))
    assert fake.calls[0][1] == 6


@pytest.mark.parametrize('text,length', [('', 'short'), ('  ', 'medium'), (None, 'long'), ('x', 'LONG'), ('x','invalid')])
def test_reject_invalid_input(text, length):
    svc, _ = service()
    with pytest.raises(SummarizationInputError):
        run(svc.summarize_async(text, length))


def test_long_input_preserves_order_and_final_pass():
    svc, fake = service()
    text = 'abcd efgh ijkl mnop qrst uvwx yz. ' * 4 + 'tail'
    result = run(svc.summarize_async(text, 'long'))
    assert result
    assert len(fake.calls) > 2
    first_round = [entry[0] for entry in fake.calls if entry[1] == 9]
    assert first_round[0].startswith('abcd')
    assert any('tail' in input_text for input_text,_ in fake.calls)
    assert fake.calls[-1][1] == 9


def test_multiple_levels_execute_and_end_with_requested_budget():
    svc, fake = service()
    text = 'abcdefghij ' * 11
    run(svc.summarize_async(text, 'short'))
    assert len(fake.calls) > 4
    assert fake.calls[-1][1] == 3
    assert all(limit == 9 for _,limit in fake.calls[:-1])


def test_no_progress_raises_not_silent_fallback():
    svc, fake = service(FakeProvider('unchanged'))
    with pytest.raises(SummarizationNoProgressError):
        run(svc.summarize_async('abcdefghijklmnop ' * 6))
    assert len(fake.calls) > 1


def test_max_depth_and_call_limit():
    svc,_=service()
    svc.MAX_HIERARCHY_LEVELS=1
    with pytest.raises(SummarizationLimitError,match='hierarchy depth'):
        run(svc.summarize_async('abcdefghijklmno ' * 10))
    svc,_=service()
    svc.MAX_MODEL_CALLS=2
    with pytest.raises(SummarizationLimitError,match='call budget'):
        run(svc.summarize_async('abcdefghijklmno ' * 10))


def test_error_and_empty_model_output_propagate():
    for mode,exception in [('error',RuntimeError),('empty',ModelOutputError)]:
        svc,_=service(FakeProvider(mode))
        with pytest.raises(exception):
            run(svc.summarize_async('سلام دنیا'))


def test_output_cap_violation_not_silently_truncated():
    svc,_=service(FakeProvider('huge'))
    with pytest.raises(SummaryOutputLimitError):
        run(svc.summarize_async('متن'))


def test_async_chunking_does_not_block_event_loop():
    svc,_=service()
    original = svc._chunker.fits
    def slow_fits(value):
        time.sleep(0.08)
        return original(value)
    svc._chunker.fits = slow_fits
    async def task():
        operation=asyncio.create_task(svc.summarize_async('متن فارسی'))
        await asyncio.sleep(0.02)
        responsive=not operation.done()
        await operation
        return responsive
    assert run(task())


def test_di_provider_graph_resolves_same_singleton():
    from src.infrastructure.di.bootstrap import bootstrap_di
    from src.infrastructure.di.inject import resolve
    from src.infrastructure.ml.mt5_model_provider import Mt5ModelProvider
    bootstrap_di()
    svc=resolve(LongTextSummarizationService)
    provider=resolve(Mt5ModelProvider)
    assert svc._provider is provider
    assert svc._chunker._model_provider is provider
    assert provider._model is None


def test_model_counting_failure_propagates():
    svc,fake=service()
    def fail(_):
        raise RuntimeError('bad tokenizer')
    fake.count_input_tokens=fail
    with pytest.raises(RuntimeError,match='bad tokenizer'):
        run(svc.summarize_async('متن'))
