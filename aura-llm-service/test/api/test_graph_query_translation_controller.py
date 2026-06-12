"""
Tests for POST /api/v1/graph-query-translation
"""
from app.domain.constants.graph.query_intent import QueryIntent
from app.domain.dtos.processing.graph_query_translation.translate_graph_query_response import TranslateGraphQueryResponse

URL = "/api/v1/graph-query-translation"

VALID_BODY = {
    "question": "¿Quién firmó el contrato con Gamma Corp?",
    "ontology": {
        "entity_types": ["PERSON", "ORGANIZATION"],
        "relation_types": ["FIRMÓ_CONTRATO_CON"],
    },
}

_RESPONSE = TranslateGraphQueryResponse(
    intent=QueryIntent.FIND_ENTITY,
    parameters={"entity_type": "PERSON"},
    confidence=0.9,
    reasoning="Se busca una entidad de tipo persona.",
)


class TestGraphQueryTranslationAuth:
    def test_missing_auth_returns_401(self, client):
        response = client.post(URL, json=VALID_BODY)
        assert response.status_code == 401

    def test_missing_permission_returns_403(self, client, make_auth_headers, mock_graph_query_translation_service):
        response = client.post(URL, json=VALID_BODY, headers=make_auth_headers(permissions=[]))
        assert response.status_code == 403

    def test_wrong_permission_returns_403(self, client, make_auth_headers, mock_graph_query_translation_service):
        response = client.post(URL, json=VALID_BODY, headers=make_auth_headers(permissions=["LLM_AGENT"]))
        assert response.status_code == 403


class TestGraphQueryTranslationValidation:
    def test_empty_question_returns_422(self, client, auth_headers, mock_graph_query_translation_service):
        body = {**VALID_BODY, "question": ""}
        response = client.post(URL, json=body, headers=auth_headers)
        assert response.status_code == 422

    def test_missing_ontology_returns_422(self, client, auth_headers, mock_graph_query_translation_service):
        response = client.post(URL, json={"question": "¿Quién?"}, headers=auth_headers)
        assert response.status_code == 422

    def test_empty_entity_types_in_ontology_returns_422(self, client, auth_headers, mock_graph_query_translation_service):
        body = {**VALID_BODY, "ontology": {"entity_types": []}}
        response = client.post(URL, json=body, headers=auth_headers)
        assert response.status_code == 422


class TestGraphQueryTranslationSuccess:
    def test_valid_request_returns_200(self, client, auth_headers, mock_graph_query_translation_service):
        mock_graph_query_translation_service.translate_graph_query.return_value = _RESPONSE
        response = client.post(URL, json=VALID_BODY, headers=auth_headers)
        assert response.status_code == 200

    def test_response_has_intent_parameters_confidence(self, client, auth_headers, mock_graph_query_translation_service):
        mock_graph_query_translation_service.translate_graph_query.return_value = _RESPONSE
        body = client.post(URL, json=VALID_BODY, headers=auth_headers).json()
        assert "intent" in body
        assert "parameters" in body
        assert "confidence" in body

    def test_service_unavailable_returns_503(self, client, auth_headers, app):
        original = getattr(app.state, "graph_query_translation_service", None)
        try:
            if hasattr(app.state, "graph_query_translation_service"):
                delattr(app.state, "graph_query_translation_service")
            response = client.post(URL, json=VALID_BODY, headers=auth_headers)
            assert response.status_code == 503
        finally:
            if original is not None:
                app.state.graph_query_translation_service = original
