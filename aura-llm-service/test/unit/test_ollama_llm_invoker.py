"""Unit tests for OllamaLLMInvoker: retry behaviour on transient transport
errors, exception wrapping, response-type guarding and content extraction."""
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.infrastructure.llm.ollama_llm.exceptions.ollama_llm_invoker_exceptions import LLMInvocationError
from app.infrastructure.llm.ollama_llm.ollama_llm_invoker import OllamaLLMInvoker
from app.infrastructure.llm.ollama_llm.ollama_llm_invoker_settings import OllamaLLMInvokerSettings


def _settings(**overrides) -> OllamaLLMInvokerSettings:
    base = dict(max_retry_attempts=3, retry_min_wait=0.1, retry_max_wait=1.0)
    base.update(overrides)
    return OllamaLLMInvokerSettings(**base)


def _llm(ainvoke: AsyncMock) -> MagicMock:
    llm = MagicMock()
    llm.ainvoke = ainvoke
    return llm


_INPUT = [HumanMessage(content="hola")]


async def test_call_llm_returns_message():
    response = AIMessage(content="respuesta")
    invoker = OllamaLLMInvoker(settings=_settings())
    result = await invoker.call_llm(_llm(AsyncMock(return_value=response)), _INPUT)
    assert result is response


async def test_transient_failure_is_retried_then_succeeds():
    response = AIMessage(content="ok")
    ainvoke = AsyncMock(side_effect=[httpx.ConnectError("boom"), response])
    invoker = OllamaLLMInvoker(settings=_settings())
    result = await invoker.call_llm(_llm(ainvoke), _INPUT)
    assert result is response
    assert ainvoke.call_count == 2


async def test_transient_failure_exhausts_retries():
    ainvoke = AsyncMock(side_effect=httpx.ReadTimeout("slow"))
    invoker = OllamaLLMInvoker(settings=_settings(max_retry_attempts=2))
    with pytest.raises(LLMInvocationError):
        await invoker.call_llm(_llm(ainvoke), _INPUT)
    assert ainvoke.call_count == 2


async def test_unexpected_error_is_wrapped_and_not_retried():
    ainvoke = AsyncMock(side_effect=ValueError("weird"))
    invoker = OllamaLLMInvoker(settings=_settings())
    with pytest.raises(LLMInvocationError):
        await invoker.call_llm(_llm(ainvoke), _INPUT)
    assert ainvoke.call_count == 1


async def test_non_message_response_raises():
    invoker = OllamaLLMInvoker(settings=_settings())
    with pytest.raises(LLMInvocationError):
        await invoker.call_llm(_llm(AsyncMock(return_value="raw string")), _INPUT)


async def test_call_llm_content_extracts_and_strips_text():
    invoker = OllamaLLMInvoker(settings=_settings())
    result = await invoker.call_llm_content(
        _llm(AsyncMock(return_value=AIMessage(content="  texto  "))), _INPUT
    )
    assert result == "texto"


async def test_call_llm_content_extracts_text_blocks_from_list():
    message = AIMessage(
        content=[
            {"type": "text", "text": "uno"},
            {"type": "tool_use", "name": "x"},
            {"type": "text", "text": "dos"},
        ]
    )
    invoker = OllamaLLMInvoker(settings=_settings())
    result = await invoker.call_llm_content(_llm(AsyncMock(return_value=message)), _INPUT)
    assert result == "uno dos"


async def test_call_llm_content_rejects_empty_response():
    invoker = OllamaLLMInvoker(settings=_settings())
    with pytest.raises(LLMInvocationError):
        await invoker.call_llm_content(
            _llm(AsyncMock(return_value=AIMessage(content="   "))), _INPUT
        )
