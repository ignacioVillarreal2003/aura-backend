"""Unit tests for DocumentContextProvider: the newly added retry on
transient/5xx POST failures (and that 4xx is NOT retried), response parsing,
fragment-count limiting, and HTTP error mapping. The HttpClient is mocked."""
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.infrastructure.http.document_context_provider.document_context_provider import DocumentContextProvider
from app.infrastructure.http.document_context_provider.document_context_provider_settings import (
    DocumentContextProviderSettings,
)
from app.infrastructure.http.document_context_provider.dtos.question_context_fragments_request import (
    QuestionContextFragmentsRequest,
    SemanticQuery,
)
from app.infrastructure.http.document_context_provider.exceptions.document_context_provider_exception import (
    DocumentContextProviderTimeoutException,
    DocumentContextProviderUnavailableException,
)
from app.infrastructure.http.http_client.exceptions.http_client_exceptions import (
    HttpClientConnectionException,
    HttpClientException,
    HttpClientServerException,
    HttpClientTimeoutException,
)


def _settings(**overrides) -> DocumentContextProviderSettings:
    base = dict(
        question_context_fragments_url="http://docs.test/by-question",
        document_context_fragments_url="http://docs.test/by-document",
        retry_max_attempts=3,
        retry_backoff_min_seconds=0.01,
        retry_backoff_max_seconds=0.02,
    )
    base.update(overrides)
    return DocumentContextProviderSettings(**base)


def _user() -> AuthenticatedUser:
    return AuthenticatedUser(id=1, email="u@test.com", roles=[], permissions=[])


def _fragment(fragment_id: int) -> dict:
    return {
        "id": fragment_id,
        "content": f"contenido-{fragment_id}",
        "fragment_index": 0,
        "document": {"id": 10, "name": "Documento"},
    }


def _ok_response(fragments: list[dict]) -> MagicMock:
    response = MagicMock()
    response.json = MagicMock(return_value={"fragments": fragments})
    return response


def _question_request() -> QuestionContextFragmentsRequest:
    return QuestionContextFragmentsRequest(
        semantic_queries=[SemanticQuery(text="pregunta", max_fragments=5)]
    )


def _provider(http, **setting_overrides) -> DocumentContextProvider:
    return DocumentContextProvider(
        http_client=http,
        document_context_provider_settings=_settings(**setting_overrides),
    )


async def test_question_retries_on_server_error_then_succeeds():
    http = MagicMock()
    http.post = AsyncMock(
        side_effect=[
            HttpClientServerException("502", status_code=502),
            _ok_response([_fragment(1)]),
        ]
    )
    provider = _provider(http)
    result = await provider.retrieve_context_fragments_by_question_request(_user(), _question_request())
    assert len(result.fragments) == 1
    assert http.post.call_count == 2


async def test_question_timeout_is_mapped_after_exhausting_retries():
    http = MagicMock()
    http.post = AsyncMock(side_effect=HttpClientTimeoutException("slow"))
    provider = _provider(http, retry_max_attempts=2)
    with pytest.raises(DocumentContextProviderTimeoutException):
        await provider.retrieve_context_fragments_by_question_request(_user(), _question_request())
    assert http.post.call_count == 2


async def test_question_4xx_is_not_retried():
    http = MagicMock()
    http.post = AsyncMock(side_effect=HttpClientException("bad request", status_code=400))
    provider = _provider(http)
    with pytest.raises(DocumentContextProviderUnavailableException):
        await provider.retrieve_context_fragments_by_question_request(_user(), _question_request())
    assert http.post.call_count == 1


async def test_document_retries_on_connection_error_then_succeeds():
    http = MagicMock()
    http.post = AsyncMock(
        side_effect=[
            HttpClientConnectionException("refused"),
            _ok_response([_fragment(1)]),
        ]
    )
    provider = _provider(http)
    result = await provider.retrieve_context_fragments_by_document(_user(), [10, 11])
    assert len(result.fragments) == 1
    assert http.post.call_count == 2


async def test_document_applies_fragment_count_limit():
    http = MagicMock()
    http.post = AsyncMock(return_value=_ok_response([_fragment(i) for i in range(1, 6)]))
    provider = _provider(http, max_fragments_per_document_response=3)
    result = await provider.retrieve_context_fragments_by_document(_user(), [10])
    assert len(result.fragments) == 3
