"""
Tests for the authentication middleware.

Uses GET /api/v1/document-query/documents as a stable authenticated endpoint.
"""
from app.configuration.environment_variables import environment_variables

_URL = "/api/v1/document-query/documents"

_BASE_HEADERS = {
    "X-Service-Api-Key": environment_variables.service_api_key,
    "X-User-Id": "42",
    "X-User-Email": "user@test.com",
}


class TestServiceApiKeyAuth:
    def test_missing_auth_returns_401(self, client):
        response = client.get(_URL)
        assert response.status_code == 401

    def test_wrong_api_key_returns_403(self, client, mock_document_query_service):
        headers = {**_BASE_HEADERS, "X-Service-Api-Key": "wrong-key"}
        response = client.get(_URL, headers=headers)
        assert response.status_code == 403

    def test_empty_api_key_returns_401(self, client, mock_document_query_service):
        headers = {**_BASE_HEADERS, "X-Service-Api-Key": ""}
        response = client.get(_URL, headers=headers)
        assert response.status_code == 401

    def test_missing_user_id_returns_400(self, client, mock_document_query_service):
        headers = {k: v for k, v in _BASE_HEADERS.items() if k != "X-User-Id"}
        response = client.get(_URL, headers=headers)
        assert response.status_code == 400

    def test_non_integer_user_id_returns_400(self, client, mock_document_query_service):
        headers = {**_BASE_HEADERS, "X-User-Id": "not-an-int"}
        response = client.get(_URL, headers=headers)
        assert response.status_code == 400

    def test_missing_user_email_returns_400(self, client, mock_document_query_service):
        headers = {k: v for k, v in _BASE_HEADERS.items() if k != "X-User-Email"}
        response = client.get(_URL, headers=headers)
        assert response.status_code == 400

    def test_valid_service_auth_passes(self, client, auth_headers, mock_document_query_service):
        response = client.get(_URL, headers=auth_headers)
        assert response.status_code not in (401, 403)


class TestPublicEndpoints:
    def test_health_skips_auth(self, client):
        assert client.get("/api/v1/health").status_code == 200

    def test_ready_skips_auth(self, client):
        assert client.get("/api/v1/ready").status_code in (200, 503)
