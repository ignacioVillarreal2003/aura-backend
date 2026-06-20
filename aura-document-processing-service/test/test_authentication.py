"""
Tests for the authentication middleware.

Uses GET /api/v1/document-query/manage/documents as a stable authenticated endpoint.
"""
_URL = "/api/v1/document-query/manage/documents"


class TestBearerTokenAuth:
    def test_missing_auth_returns_401(self, client):
        response = client.get(_URL)
        assert response.status_code == 401

    def test_non_bearer_authorization_returns_401(self, client, mock_document_query_service):
        response = client.get(_URL, headers={"Authorization": "Basic abc123"})
        assert response.status_code == 401

    def test_invalid_token_returns_401(self, client, mock_document_query_service):
        response = client.get(_URL, headers={"Authorization": "Bearer not-a-valid-token"})
        assert response.status_code == 401

    def test_valid_token_passes(self, client, auth_headers, mock_document_query_service):
        response = client.get(_URL, headers=auth_headers)
        assert response.status_code not in (401, 403)

    def test_valid_token_without_permissions_returns_403(self, client, service_headers, mock_document_query_service):
        response = client.get(_URL, headers=service_headers(permissions=[]))
        assert response.status_code == 403


class TestPublicEndpoints:
    def test_health_skips_auth(self, client):
        assert client.get("/api/v1/health").status_code == 200

    def test_ready_skips_auth(self, client):
        assert client.get("/api/v1/ready").status_code in (200, 503)
