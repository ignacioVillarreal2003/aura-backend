"""
Tests for POST /api/v1/graph-extraction
"""
from app.domain.dtos.processing.graph_extraction.extract_entities_relations_response import ExtractEntitiesRelationsResponse

URL = "/api/v1/graph-extraction"

VALID_BODY = {
    "content": "La empresa Acme S.A. firmó un contrato con Gamma Corp el 10 de enero de 2024.",
    "document_id": 1,
    "fragment_id": 1,
    "allowed_entity_types": ["ORGANIZATION", "DATE"],
    "allowed_relation_types": ["FIRMÓ_CONTRATO_CON"],
}

_RESPONSE = ExtractEntitiesRelationsResponse(entities=[], relations=[])


class TestGraphExtractionAuth:
    def test_missing_auth_returns_401(self, client):
        response = client.post(URL, json=VALID_BODY)
        assert response.status_code == 401

    def test_missing_permission_returns_403(self, client, make_auth_headers, mock_graph_extraction_service):
        response = client.post(URL, json=VALID_BODY, headers=make_auth_headers(permissions=[]))
        assert response.status_code == 403

    def test_wrong_permission_returns_403(self, client, make_auth_headers, mock_graph_extraction_service):
        response = client.post(URL, json=VALID_BODY, headers=make_auth_headers(permissions=["LLM_AGENT"]))
        assert response.status_code == 403


class TestGraphExtractionValidation:
    def test_empty_entity_types_returns_422(self, client, auth_headers, mock_graph_extraction_service):
        body = {**VALID_BODY, "allowed_entity_types": []}
        response = client.post(URL, json=body, headers=auth_headers)
        assert response.status_code == 422

    def test_zero_document_id_returns_422(self, client, auth_headers, mock_graph_extraction_service):
        body = {**VALID_BODY, "document_id": 0}
        response = client.post(URL, json=body, headers=auth_headers)
        assert response.status_code == 422

    def test_zero_fragment_id_returns_422(self, client, auth_headers, mock_graph_extraction_service):
        body = {**VALID_BODY, "fragment_id": 0}
        response = client.post(URL, json=body, headers=auth_headers)
        assert response.status_code == 422

    def test_missing_content_returns_422(self, client, auth_headers, mock_graph_extraction_service):
        body = {k: v for k, v in VALID_BODY.items() if k != "content"}
        response = client.post(URL, json=body, headers=auth_headers)
        assert response.status_code == 422


class TestGraphExtractionSuccess:
    def test_valid_request_returns_200(self, client, auth_headers, mock_graph_extraction_service):
        mock_graph_extraction_service.extract_entities_relations.return_value = _RESPONSE
        response = client.post(URL, json=VALID_BODY, headers=auth_headers)
        assert response.status_code == 200

    def test_response_has_entities_and_relations(self, client, auth_headers, mock_graph_extraction_service):
        mock_graph_extraction_service.extract_entities_relations.return_value = _RESPONSE
        body = client.post(URL, json=VALID_BODY, headers=auth_headers).json()
        assert "entities" in body
        assert "relations" in body

    def test_service_unavailable_returns_503(self, client, auth_headers, app):
        original = getattr(app.state, "graph_extraction_service", None)
        try:
            if hasattr(app.state, "graph_extraction_service"):
                delattr(app.state, "graph_extraction_service")
            response = client.post(URL, json=VALID_BODY, headers=auth_headers)
            assert response.status_code == 503
        finally:
            if original is not None:
                app.state.graph_extraction_service = original
