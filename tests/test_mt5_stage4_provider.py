"""Additional backward-compatible provider token-count and length tests."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
import sys
from types import ModuleType
from unittest.mock import Mock

import pytest

from src.infrastructure.ml.mt5_model_provider import (
    ModelInferenceError, ModelInputError, ModelLoadError, Mt5ModelProvider,
)
from src.infrastructure.utils.config_reader import ConfigReader


class FakeTensor:
    shape = (1, 10)
    def to(self, _):
        return self


@pytest.fixture
def backend(monkeypatch):
    tokenizer = Mock()
    def encode(text, **kw):
        if kw['return_tensors'] is None:
            return {'input_ids': list(range(len(text) + 1))}
        return {'input_ids': FakeTensor(), 'attention_mask': FakeTensor()}
    tokenizer.side_effect = encode
    tokenizer.decode.return_value = 'خلاصه فارسی'
    tokenizer_factory = Mock()
    tokenizer_factory.from_pretrained.return_value = tokenizer
    model = Mock()
    model.generate.return_value = [[1,2,3]]
    model_factory = Mock()
    model_factory.from_pretrained.return_value = model
    transformers = ModuleType('transformers')
    transformers.AutoTokenizer = tokenizer_factory
    transformers.AutoModelForSeq2SeqLM = model_factory
    torch = ModuleType('torch')
    torch.inference_mode = nullcontext
    torch.cuda = Mock()
    torch.cuda.is_available.return_value = False
    monkeypatch.setitem(sys.modules,'transformers',transformers)
    monkeypatch.setitem(sys.modules,'torch',torch)
    return tokenizer, tokenizer_factory, model_factory, model


def provider():
    return Mt5ModelProvider(ConfigReader())


def test_count_input_uses_exact_specials_without_weights(backend):
    tokenizer, tokenizer_factory, model_factory, _ = backend
    p = provider()
    assert p.count_input_tokens('  متن  ') == 4
    assert p._model is None
    assert tokenizer_factory.from_pretrained.call_count == 1
    assert model_factory.from_pretrained.call_count == 0
    args = tokenizer.call_args.kwargs
    assert args['add_special_tokens'] is True
    assert args['padding'] is False
    assert args['truncation'] is False
    assert args['return_tensors'] is None


def test_token_count_uses_cached_tokenizer_when_model_later_loads(backend):
    _, tokenizer_factory, model_factory, model = backend
    p=provider()
    p.count_input_tokens('متن')
    p.summarize('متن')
    p.count_input_tokens('متن')
    assert tokenizer_factory.from_pretrained.call_count == 1
    assert model_factory.from_pretrained.call_count == 1
    assert model.generate.call_args.kwargs['max_length'] == 120


def test_count_concurrent_keeps_single_tokenizer(backend):
    _,tokenizer_factory,model_factory,_=backend
    p=provider()
    with ThreadPoolExecutor(max_workers=8) as pool:
        assert list(pool.map(p.count_input_tokens, ['abc']*20)) == [4]*20
    assert tokenizer_factory.from_pretrained.call_count == 1
    assert model_factory.from_pretrained.call_count == 0


def test_optional_generation_max_preserves_old_contract(backend):
    _,_,_,model=backend
    p=provider()
    assert p.summarize('سلام')
    assert model.generate.call_args.kwargs['max_length']==120
    assert p.summarize('سلام',max_output_tokens=40)
    assert model.generate.call_args.kwargs['max_length']==40
    assert asyncio.run(p.summarize_async('سلام',max_output_tokens=80))
    assert model.generate.call_args.kwargs['max_length']==80


@pytest.mark.parametrize('bad', [0,121,-1,True,3.0,'40'])
def test_reject_invalid_output_budget_without_loading(backend,bad):
    p=provider()
    with pytest.raises(ModelInputError,match='max_output_tokens'):
        p.summarize('متن',max_output_tokens=bad)
    assert p._model is None


def test_tokenizer_load_failure_is_cached_without_model_load(backend):
    _,factory,model_factory,_=backend
    factory.from_pretrained.side_effect=OSError('private path')
    p=provider()
    for _ in range(2):
        with pytest.raises(ModelLoadError,match='tokenizer') as exc:
            p.count_input_tokens('متن')
        assert 'private path' not in str(exc.value)
    assert factory.from_pretrained.call_count==1
    assert model_factory.from_pretrained.call_count==0


def test_token_count_invalid_input_without_loading(backend):
    p=provider()
    for invalid in ('  ',None,123,'x'*20001):
        with pytest.raises(ModelInputError):
            p.count_input_tokens(invalid)
    assert p._tokenizer is None


def test_tokenizer_encoding_error_is_wrapped(backend):
    tokenizer,*_=backend
    tokenizer.side_effect=RuntimeError('private text')
    with pytest.raises(ModelInferenceError,match='token counting') as exc:
        provider().count_input_tokens('محرمانه')
    assert 'private text' not in str(exc.value)
