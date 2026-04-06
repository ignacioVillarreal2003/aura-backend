"""Unit tests for LlmProvider with mocked HTTP client."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.constants.document.document_type import DocumentType
from app.infrastructure.http.http_client.exceptions.http_client_exceptions import (
    HttpClientTimeoutException,
)
from app.infrastructure.http.llm_provider.exceptions.llm_provider_exception import (
    LlmProviderInvalidResponseException,
)
from app.infrastructure.http.llm_provider.llm_provider import LlmProvider
from app.infrastructure.http.llm_provider.llm_provider_settings import LlmProviderSettings


def _user() -> AuthenticatedUser:
    return AuthenticatedUser(id=1, email="u@test.dev", roles=["user"], permissions=[])


def _settings() -> LlmProviderSettings:
    return LlmProviderSettings(
        classify_document_url="http://localhost:9999/classify",
        enrich_fragment_url="http://localhost:9999/enrich",
        timeout_seconds=30.0,
    )


@pytest.mark.asyncio
async def test_classify_document_success() -> None:
    resp = MagicMock()
    resp.json.return_value = {
        "type": "otro",
        "category": "cat",
        "description": "desc",
    }
    http = AsyncMock()
    http.post = AsyncMock(return_value=resp)
    provider = LlmProvider(http, _settings())
    out = await provider.classify_document("doc.pdf", "body text", _user())
    assert out.type == DocumentType.otro
    assert out.category == "cat"
    http.post.assert_awaited_once()


@pytest.mark.asyncio
async def test_classify_document_timeout_propagates() -> None:
    http = AsyncMock()
    http.post = AsyncMock(side_effect=HttpClientTimeoutException("timeout"))
    provider = LlmProvider(http, _settings())
    with pytest.raises(HttpClientTimeoutException):
        await provider.classify_document("x", "y", _user())


@pytest.mark.asyncio
async def test_classify_document_invalid_json_raises() -> None:
    resp = MagicMock()
    resp.json.return_value = {"type": "bad", "category": 1, "description": None}
    http = AsyncMock()
    http.post = AsyncMock(return_value=resp)
    provider = LlmProvider(http, _settings())
    with pytest.raises(LlmProviderInvalidResponseException):
        await provider.classify_document("x", "y", _user())


@pytest.mark.asyncio
async def test_enrich_fragment_success() -> None:
    resp = MagicMock()
    resp.json.return_value = {
        "summary": "s",
        "entities": {"a": 1},
        "topics": ["t1"],
    }
    http = AsyncMock()
    http.post = AsyncMock(return_value=resp)
    provider = LlmProvider(http, _settings())
    out = await provider.enrich_fragment("fragment text", _user())
    assert out.summary == "s"
    assert out.topics == ["t1"]
