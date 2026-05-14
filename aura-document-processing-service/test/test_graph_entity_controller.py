"""
Tests for GET /api/v1/graph/entity/{name}
"""
from app.domain.constants.graph.entity_type import EntityType
from app.domain.dtos.graph.graph_entity.graph_entity_response import GraphEntityResponse
from app.domain.dtos.graph.graph_entity.graph_entity_with_relations_response import (
    GraphEntityWithRelationsResponse,
)

URL = "/api/v1/graph/entity/Gamma%20Corp"

_ENTITY = GraphEntityResponse(
    canonical_name="Gamma Corp",
    display_name="Gamma Corp",
    type=EntityType.ORGANIZATION,
)

_RESPONSE = GraphEntityWithRelationsResponse(entity=_ENTITY, relations=[])


class TestGraphEntityAuth:
    def test_missing_auth_returns_401(self, client):
        assert client.get(URL).status_code == 401


class TestGraphEntityValidation:
    def test_depth_above_max_returns_422(self, client, auth_headers, mock_graph_entity_service):
        response = client.get(URL, params={"depth": 7}, headers=auth_headers)
        assert response.status_code == 422

    def test_depth_zero_returns_422(self, client, auth_headers, mock_graph_entity_service):
        response = client.get(URL, params={"depth": 0}, headers=auth_headers)
        assert response.status_code == 422

    def test_invalid_entity_type_returns_422(self, client, auth_headers, mock_graph_entity_service):
        response = client.get(URL, params={"type": "invalid_type"}, headers=auth_headers)
        assert response.status_code == 422


class TestGraphEntitySuccess:
    def test_valid_request_returns_200(self, client, auth_headers, mock_graph_entity_service):
        mock_graph_entity_service.get_entity_with_relations.return_value = _RESPONSE
        assert client.get(URL, headers=auth_headers).status_code == 200

    def test_response_has_entity_and_relations(self, client, auth_headers, mock_graph_entity_service):
        mock_graph_entity_service.get_entity_with_relations.return_value = _RESPONSE
        body = client.get(URL, headers=auth_headers).json()
        assert "entity" in body
        assert "relations" in body

    def test_accepts_optional_type_and_depth(self, client, auth_headers, mock_graph_entity_service):
        mock_graph_entity_service.get_entity_with_relations.return_value = _RESPONSE
        response = client.get(URL, params={"type": "organization", "depth": 2}, headers=auth_headers)
        assert response.status_code == 200

    def test_service_unavailable_returns_503(self, client, auth_headers, app):
        original = getattr(app.state, "graph_entity_service", None)
        try:
            if hasattr(app.state, "graph_entity_service"):
                delattr(app.state, "graph_entity_service")
            assert client.get(URL, headers=auth_headers).status_code == 503
        finally:
            if original is not None:
                app.state.graph_entity_service = original
