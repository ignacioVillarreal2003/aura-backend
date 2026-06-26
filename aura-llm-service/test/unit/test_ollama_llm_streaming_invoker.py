"""Unit tests for OllamaLLMStreamingInvoker: chunk-to-text extraction,
non-text block skipping, the response-size cap, retry while establishing the
stream, and mid-stream failure handling."""
from unittest.mock import MagicMock

import httpx
import pytest
from langchain_core.messages import HumanMessage

from app.infrastructure.llm.ollama_llm.exceptions.ollama_llm_invoker_exceptions import LLMInvocationError
from app.infrastructure.llm.ollama_llm.ollama_llm_invoker_settings import OllamaLLMInvokerSettings
from app.infrastructure.llm.ollama_llm.ollama_llm_streaming_invoker import OllamaLLMStreamingInvoker


def _settings(**overrides) -> OllamaLLMInvokerSettings:
    base = dict(max_retry_attempts=3, retry_min_wait=0.1, retry_max_wait=1.0)
    base.update(overrides)
    return OllamaLLMInvokerSettings(**base)


class _Chunk:
    def __init__(self, content) -> None:
        self.content = content


def _streaming_llm(chunk_contents, *, fail_times=0):
    """Build a fake LLM whose ``astream`` raises ``fail_times`` times (before
    yielding the first chunk) and then streams ``chunk_contents``."""
    calls = {"n": 0}

    def astream(_llm_input):
        async def gen():
            calls["n"] += 1
            if calls["n"] <= fail_times:
                raise httpx.ConnectError("boom")
            for content in chunk_contents:
                yield _Chunk(content)

        return gen()

    llm = MagicMock()
    llm.astream = astream
    return llm, calls


_INPUT = [HumanMessage(content="hola")]


async def _collect(invoker, llm):
    return [text async for text in invoker.stream_llm_content(llm, _INPUT)]


async def test_stream_yields_text_chunks():
    llm, _ = _streaming_llm(["a", "b", "c"])
    invoker = OllamaLLMStreamingInvoker(settings=_settings())
    assert await _collect(invoker, llm) == ["a", "b", "c"]


async def test_empty_stream_yields_nothing():
    llm, _ = _streaming_llm([])
    invoker = OllamaLLMStreamingInvoker(settings=_settings())
    assert await _collect(invoker, llm) == []


async def test_non_text_blocks_are_skipped():
    content = [{"type": "reasoning", "text": "oculto"}, {"type": "text", "text": "visible"}]
    llm, _ = _streaming_llm([content])
    invoker = OllamaLLMStreamingInvoker(settings=_settings())
    assert await _collect(invoker, llm) == ["visible"]


async def test_transient_failure_before_first_chunk_is_retried():
    llm, calls = _streaming_llm(["x", "y"], fail_times=1)
    invoker = OllamaLLMStreamingInvoker(settings=_settings())
    assert await _collect(invoker, llm) == ["x", "y"]
    assert calls["n"] == 2


async def test_response_size_cap_is_enforced():
    llm, _ = _streaming_llm(["a" * 1500])
    invoker = OllamaLLMStreamingInvoker(settings=_settings(max_stream_response_chars=1000))
    with pytest.raises(LLMInvocationError):
        await _collect(invoker, llm)


async def test_mid_stream_failure_raises_after_partial_output():
    def astream(_llm_input):
        async def gen():
            yield _Chunk("ok")
            raise httpx.ReadTimeout("dropped")

        return gen()

    llm = MagicMock()
    llm.astream = astream
    invoker = OllamaLLMStreamingInvoker(settings=_settings())

    collected = []
    with pytest.raises(LLMInvocationError):
        async for text in invoker.stream_llm_content(llm, _INPUT):
            collected.append(text)
    assert collected == ["ok"]
