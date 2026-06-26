"""Unit tests for GraphContextProvider: inactive short-circuiting, fail-soft
behaviour (errors degrade to empty results), the newly added retry on
transient/5xx POST failures, query-URL derivation, and structured fact
rendering. The HttpClient is mocked."""
from unittest.mock import AsyncMock, MagicMock

from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.infrastructure.http.graph_context_provider.graph_context_provider import GraphContextProvider
from app.infrastructure.http.graph_context_provider.graph_context_provider_settings import (
    GraphContextProviderSettings,
)
from app.infrastructure.http.http_client.exceptions.http_client_exceptions import (
    HttpClientServerException,
    HttpClientTimeoutException,
)


def _settings(**overrides) -> GraphContextProviderSettings:
    base = dict(
        url="http://graph.test/context",
        retry_max_attempts=3,
        retry_backoff_min_seconds=0.01,
        retry_backoff_max_seconds=0.02,
    )
    base.update(overrides)
    return GraphContextProviderSettings(**base)


def _user() -> AuthenticatedUser:
    return AuthenticatedUser(id=1, email="u@test.com", roles=[], permissions=[])


def _json_response(payload: dict) -> MagicMock:
    response = MagicMock()
    response.json = MagicMock(return_value=payload)
    return response


def _provider(http, **setting_overrides) -> GraphContextProvider:
    return GraphContextProvider(
        http_client=http,
        graph_context_provider_settings=_settings(**setting_overrides),
    )


async def test_inactive_provider_returns_empty_without_calling():
    http = MagicMock()
    http.post = AsyncMock()
    provider = GraphContextProvider(
        http_client=http,
        graph_context_provider_settings=GraphContextProviderSettings(enabled=False),
    )
    result = await provider.retrieve_graph_context(authenticated_user=_user(), question="q", terms=["t"])
    assert result.context_text == ""
    assert result.facts == []
    http.post.assert_not_called()


async def test_empty_query_returns_empty_without_calling():
    http = MagicMock()
    http.post = AsyncMock()
    provider = _provider(http)
    result = await provider.retrieve_graph_context(authenticated_user=_user(), question="   ", terms=[])
    assert result.context_text == ""
    http.post.assert_not_called()


async def test_retrieve_graph_context_success():
    http = MagicMock()
    http.post = AsyncMock(
        return_value=_json_response(
            {
                "context_text": "hechos del grafo",
                "facts": [{"text": "f1", "source_document_ids": [1]}],
                "matched_terms": ["t"],
            }
        )
    )
    provider = _provider(http)
    result = await provider.retrieve_graph_context(authenticated_user=_user(), question="q", terms=["t"])
    assert result.context_text == "hechos del grafo"
    assert len(result.facts) == 1
    assert result.matched_terms == ["t"]


async def test_retrieve_graph_context_retries_on_server_error():
    http = MagicMock()
    http.post = AsyncMock(
        side_effect=[
            HttpClientServerException("503", status_code=503),
            _json_response({"context_text": "ok", "facts": [], "matched_terms": []}),
        ]
    )
    provider = _provider(http)
    result = await provider.retrieve_graph_context(authenticated_user=_user(), question="q", terms=["t"])
    assert result.context_text == "ok"
    assert http.post.call_count == 2


async def test_retrieve_graph_context_is_fail_soft_after_retries():
    http = MagicMock()
    http.post = AsyncMock(side_effect=HttpClientTimeoutException("slow"))
    provider = _provider(http, retry_max_attempts=2)
    result = await provider.retrieve_graph_context(authenticated_user=_user(), question="q", terms=["t"])
    assert result.context_text == ""
    assert http.post.call_count == 2


async def test_execute_graph_query_renders_entities_and_relations():
    http = MagicMock()
    http.post = AsyncMock(
        return_value=_json_response(
            {
                "entities": [{"display_name": "Ana", "type": "Person", "description": "ingeniera"}],
                "relations": [
                    {
                        "type": "works_at",
                        "source": {"display_name": "Ana", "type": "Person"},
                        "target": {"display_name": "Acme", "type": "Org"},
                    }
                ],
            }
        )
    )
    provider = _provider(http)
    result = await provider.execute_graph_query(authenticated_user=_user(), question="q")
    assert result.entities_count == 1
    assert result.relations_count == 1
    assert "Ana (Person): ingeniera" in result.context_text
    assert "works at" in result.context_text


def test_resolve_query_url_derives_from_context_url():
    settings = GraphContextProviderSettings(url="http://graph.test/context")
    assert settings.resolve_query_url == "http://graph.test/query"


def test_resolve_query_url_prefers_explicit_value():
    settings = GraphContextProviderSettings(
        url="http://graph.test/context",
        query_url="http://graph.test/custom-query",
    )
    assert settings.resolve_query_url == "http://graph.test/custom-query"
