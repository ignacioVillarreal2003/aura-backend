"""
Tests for POST /api/v1/graph/path
"""
from app.domain.dtos.graph.graph_path.graph_path_response import FindPathResponse

URL = "/api/v1/graph/path"

VALID_BODY = {
    "source_name": "Juan Pérez",
    "target_name": "Gamma Corp",
    "max_hops": 4,
    "max_paths": 5,
    "only_shortest": False,
}

_RESPONSE = FindPathResponse(paths=[], truncated=False)


class TestGraphPathAuth:
    def test_missing_auth_returns_401(self, client):
        assert client.post(URL, json=VALID_BODY).status_code == 401


class TestGraphPathValidation:
    def test_missing_source_name_returns_422(self, client, auth_headers, mock_graph_path_service):
        body = {k: v for k, v in VALID_BODY.items() if k != "source_name"}
        assert client.post(URL, json=body, headers=auth_headers).status_code == 422

    def test_missing_target_name_returns_422(self, client, auth_headers, mock_graph_path_service):
        body = {k: v for k, v in VALID_BODY.items() if k != "target_name"}
        assert client.post(URL, json=body, headers=auth_headers).status_code == 422

    def test_empty_source_name_returns_422(self, client, auth_headers, mock_graph_path_service):
        body = {**VALID_BODY, "source_name": ""}
        assert client.post(URL, json=body, headers=auth_headers).status_code == 422

    def test_same_source_and_target_returns_422(self, client, auth_headers, mock_graph_path_service):
        body = {**VALID_BODY, "source_name": "Gamma Corp", "target_name": "Gamma Corp"}
        assert client.post(URL, json=body, headers=auth_headers).status_code == 422

    def test_max_hops_above_limit_returns_422(self, client, auth_headers, mock_graph_path_service):
        body = {**VALID_BODY, "max_hops": 7}
        assert client.post(URL, json=body, headers=auth_headers).status_code == 422

    def test_max_hops_zero_returns_422(self, client, auth_headers, mock_graph_path_service):
        body = {**VALID_BODY, "max_hops": 0}
        assert client.post(URL, json=body, headers=auth_headers).status_code == 422

    def test_max_paths_above_limit_returns_422(self, client, auth_headers, mock_graph_path_service):
        body = {**VALID_BODY, "max_paths": 26}
        assert client.post(URL, json=body, headers=auth_headers).status_code == 422


class TestGraphPathSuccess:
    def test_valid_request_returns_200(self, client, auth_headers, mock_graph_path_service):
        mock_graph_path_service.find_paths.return_value = _RESPONSE
        assert client.post(URL, json=VALID_BODY, headers=auth_headers).status_code == 200

    def test_response_has_paths_and_truncated(self, client, auth_headers, mock_graph_path_service):
        mock_graph_path_service.find_paths.return_value = _RESPONSE
        body = client.post(URL, json=VALID_BODY, headers=auth_headers).json()
        assert "paths" in body
        assert "truncated" in body

    def test_only_shortest_flag_accepted(self, client, auth_headers, mock_graph_path_service):
        mock_graph_path_service.find_paths.return_value = _RESPONSE
        body = {**VALID_BODY, "only_shortest": True}
        assert client.post(URL, json=body, headers=auth_headers).status_code == 200

    def test_optional_type_fields_accepted(self, client, auth_headers, mock_graph_path_service):
        mock_graph_path_service.find_paths.return_value = _RESPONSE
        body = {**VALID_BODY, "source_type": "person", "target_type": "organization"}
        assert client.post(URL, json=body, headers=auth_headers).status_code == 200

    def test_service_unavailable_returns_503(self, client, auth_headers, app):
        original = getattr(app.state, "graph_path_service", None)
        try:
            if hasattr(app.state, "graph_path_service"):
                delattr(app.state, "graph_path_service")
            assert client.post(URL, json=VALID_BODY, headers=auth_headers).status_code == 503
        finally:
            if original is not None:
                app.state.graph_path_service = original
