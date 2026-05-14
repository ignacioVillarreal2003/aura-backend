"""
Tests for POST /api/v1/graph/query
"""
from app.domain.constants.graph.query_intent import QueryIntent
from app.domain.dtos.graph.graph_query.graph_query_response import GraphQueryResponse

URL = "/api/v1/graph/query"

VALID_BODY = {
    "question": "¿Quién firmó el contrato con Gamma Corp?",
    "max_results": 10,
}

_RESPONSE = GraphQueryResponse(
    intent=QueryIntent.FIND_ENTITY,
    confidence=0.9,
    entities=[],
    relations=[],
    explanation="Se detectó una búsqueda de entidad.",
)


class TestGraphQueryAuth:
    def test_missing_auth_returns_401(self, client):
        assert client.post(URL, json=VALID_BODY).status_code == 401


class TestGraphQueryValidation:
    def test_empty_question_returns_422(self, client, auth_headers, mock_graph_query_service):
        response = client.post(URL, json={"question": ""}, headers=auth_headers)
        assert response.status_code == 422

    def test_missing_question_returns_422(self, client, auth_headers, mock_graph_query_service):
        response = client.post(URL, json={}, headers=auth_headers)
        assert response.status_code == 422

    def test_max_results_zero_returns_422(self, client, auth_headers, mock_graph_query_service):
        response = client.post(URL, json={**VALID_BODY, "max_results": 0}, headers=auth_headers)
        assert response.status_code == 422

    def test_max_results_above_limit_returns_422(self, client, auth_headers, mock_graph_query_service):
        response = client.post(URL, json={**VALID_BODY, "max_results": 201}, headers=auth_headers)
        assert response.status_code == 422


class TestGraphQuerySuccess:
    def test_valid_request_returns_200(self, client, auth_headers, mock_graph_query_service):
        mock_graph_query_service.execute.return_value = _RESPONSE
        assert client.post(URL, json=VALID_BODY, headers=auth_headers).status_code == 200

    def test_response_has_intent_confidence_entities_relations(self, client, auth_headers, mock_graph_query_service):
        mock_graph_query_service.execute.return_value = _RESPONSE
        body = client.post(URL, json=VALID_BODY, headers=auth_headers).json()
        assert "intent" in body
        assert "confidence" in body
        assert "entities" in body
        assert "relations" in body

    def test_service_unavailable_returns_503(self, client, auth_headers, app):
        original = getattr(app.state, "graph_query_service", None)
        try:
            if hasattr(app.state, "graph_query_service"):
                delattr(app.state, "graph_query_service")
            assert client.post(URL, json=VALID_BODY, headers=auth_headers).status_code == 503
        finally:
            if original is not None:
                app.state.graph_query_service = original
