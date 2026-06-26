"""Unit tests for OllamaLLMFacade: connectivity probing, model availability
matching, the initialization circuit breaker, and the call-time option override
that couples to a langchain-ollama internal (_chat_params)."""
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from langchain_core.messages import HumanMessage

from app.infrastructure.llm.ollama_llm.exceptions.ollama_llm_facade_exceptions import (
    LLMInitializationError,
    LLMNotConfiguredError,
)
from app.infrastructure.llm.ollama_llm.ollama_llm_facade import (
    OllamaLLMFacade,
    _ChatOllamaWithCallTimeOptions,
)
from app.infrastructure.llm.ollama_llm.ollama_llm_facade_settings import OllamaLLMFacadeSettings


def _facade(**setting_overrides) -> OllamaLLMFacade:
    settings = OllamaLLMFacadeSettings(
        model_name="test-model",
        base_url="http://ollama.test",
        **setting_overrides,
    )
    return OllamaLLMFacade(ollama_llm_facade_settings=settings)


def _tags_response(model_names) -> MagicMock:
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json = MagicMock(return_value={"models": [{"name": name} for name in model_names]})
    return response


def _install_probe(facade: OllamaLLMFacade, *, response=None, side_effect=None) -> MagicMock:
    fake = MagicMock()
    fake.get = AsyncMock(return_value=response, side_effect=side_effect)
    fake.aclose = AsyncMock()
    facade._probe_client = fake
    return fake


async def test_initialize_succeeds_when_model_available():
    facade = _facade()
    _install_probe(facade, response=_tags_response(["test-model"]))
    await facade.initialize()
    try:
        assert facade.is_healthy() is True
        assert await facade.get_llm_base() is not None
        assert await facade.get_llm_json() is not None
    finally:
        await facade.aclose()


async def test_initialize_accepts_latest_tag_match():
    facade = _facade()
    _install_probe(facade, response=_tags_response(["test-model:latest"]))
    await facade.initialize()
    try:
        assert facade.is_healthy() is True
    finally:
        await facade.aclose()


async def test_initialize_fails_when_model_missing():
    facade = _facade()
    _install_probe(facade, response=_tags_response(["other-model"]))
    with pytest.raises(LLMInitializationError):
        await facade.initialize()
    assert facade.is_healthy() is False


async def test_initialize_fails_on_probe_connection_error():
    facade = _facade()
    _install_probe(facade, side_effect=httpx.ConnectError("down"))
    with pytest.raises(LLMInitializationError):
        await facade.initialize()
    assert facade.is_healthy() is False


async def test_circuit_opens_after_threshold_and_blocks_further_attempts():
    facade = _facade(circuit_failure_threshold=2, circuit_recovery_cooldown_seconds=30.0)
    _install_probe(facade, side_effect=httpx.ConnectError("down"))

    for _ in range(2):
        with pytest.raises(LLMInitializationError):
            await facade.initialize()

    with pytest.raises(LLMNotConfiguredError):
        await facade.initialize()


async def test_get_llm_with_tools_returns_base_when_no_tools():
    facade = _facade()
    _install_probe(facade, response=_tags_response(["test-model"]))
    await facade.initialize()
    try:
        base = await facade.get_llm_base()
        with_tools = await facade.get_llm_with_tools()
        assert with_tools is base
        assert facade.tools_bound is False
    finally:
        await facade.aclose()


async def test_check_health_is_false_before_init_and_true_after():
    facade = _facade()
    assert await facade.check_health() is False
    _install_probe(facade, response=_tags_response(["test-model"]))
    await facade.initialize()
    try:
        assert await facade.check_health() is True
    finally:
        await facade.aclose()


def test_chat_params_merges_call_time_options():
    llm = _ChatOllamaWithCallTimeOptions(model="test-model", base_url="http://ollama.test")
    params = llm._chat_params([HumanMessage(content="hola")], temperature=0.1, num_predict=8)
    assert params["options"]["temperature"] == 0.1
    assert params["options"]["num_predict"] == 8


def test_chat_params_maps_max_tokens_alias_to_num_predict():
    llm = _ChatOllamaWithCallTimeOptions(model="test-model", base_url="http://ollama.test")
    params = llm._chat_params([HumanMessage(content="hola")], max_tokens=32)
    assert params["options"]["num_predict"] == 32
