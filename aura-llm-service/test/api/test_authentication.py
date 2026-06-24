"""
Tests for the AuthenticationProviderMiddleware behaviour on protected routes.

Authentication is JWT-only: the middleware extracts the bearer token and asks
the AuthenticationProvider to resolve it (Redis cache first, auth service on
miss). Uses /api/v1/document-classify as a representative protected endpoint.
"""
from app.infrastructure.http.authentication_provider.exceptions.authentication_provider_exception import (
    AuthenticationProviderInvalidTokenException,
    AuthenticationProviderServiceUnavailableException,
    AuthenticationProviderUnauthorizedException,
    AuthenticationProviderUserNotFoundException,
)

PROTECTED_URL = "/api/v1/document-classify"

VALID_BODY = {
    "document_name": "contrato_001.pdf",
    "content": "Este es el contenido del documento de prueba.",
}


class TestJwtAuthentication:
    def test_missing_token_returns_401(self, client):
        response = client.post(PROTECTED_URL, json=VALID_BODY)
        assert response.status_code == 401
        assert response.json()["error"] == "missing_token"

    def test_non_bearer_authorization_returns_401(self, client):
        response = client.post(
            PROTECTED_URL, json=VALID_BODY, headers={"Authorization": "Basic abc123"}
        )
        assert response.status_code == 401

    def test_legacy_service_headers_are_ignored(self, client):
        headers = {
            "X-Service-Api-Key": "any-key",
            "X-User-Id": "42",
            "X-User-Email": "user@test.com",
            "X-User-Permissions": "LLM_DOCUMENT_CLASSIFY",
        }
        response = client.post(PROTECTED_URL, json=VALID_BODY, headers=headers)
        assert response.status_code == 401

    def test_invalid_token_returns_401(self, client, mock_authentication_provider):
        mock_authentication_provider.validate_token.side_effect = (
            AuthenticationProviderInvalidTokenException("Invalid or expired token")
        )
        response = client.post(
            PROTECTED_URL, json=VALID_BODY, headers={"Authorization": "Bearer bad-token"}
        )
        assert response.status_code == 401
        assert response.json()["error"] == "invalid_token"

    def test_forbidden_token_returns_403(self, client, mock_authentication_provider):
        mock_authentication_provider.validate_token.side_effect = (
            AuthenticationProviderUnauthorizedException("Access forbidden")
        )
        response = client.post(
            PROTECTED_URL, json=VALID_BODY, headers={"Authorization": "Bearer some-token"}
        )
        assert response.status_code == 403

    def test_user_not_found_returns_404(self, client, mock_authentication_provider):
        mock_authentication_provider.validate_token.side_effect = (
            AuthenticationProviderUserNotFoundException("User not found")
        )
        response = client.post(
            PROTECTED_URL, json=VALID_BODY, headers={"Authorization": "Bearer some-token"}
        )
        assert response.status_code == 404

    def test_auth_service_unavailable_returns_503(self, client, mock_authentication_provider):
        mock_authentication_provider.validate_token.side_effect = (
            AuthenticationProviderServiceUnavailableException("down")
        )
        response = client.post(
            PROTECTED_URL, json=VALID_BODY, headers={"Authorization": "Bearer some-token"}
        )
        assert response.status_code == 503

    def test_valid_token_passes_middleware(
            self, client, make_auth_headers, mock_document_classify_service
    ):
        from app.domain.constants.document_type import DocumentType
        from app.domain.dtos.processing.document_classify.classify_document_response import (
            ClassifyDocumentResponse,
        )

        mock_document_classify_service.classify_document.return_value = ClassifyDocumentResponse(
            type=DocumentType.informe,
            category="Legal",
            description="Documento legal de prueba.",
        )
        headers = make_auth_headers(permissions=["LLM_DOCUMENT_CLASSIFY"])
        response = client.post(PROTECTED_URL, json=VALID_BODY, headers=headers)
        assert response.status_code == 200

    def test_provider_receives_the_bearer_token(
            self, client, make_auth_headers, mock_authentication_provider, mock_document_classify_service
    ):
        headers = make_auth_headers(permissions=["LLM_DOCUMENT_CLASSIFY"])
        client.post(PROTECTED_URL, json=VALID_BODY, headers=headers)
        mock_authentication_provider.validate_token.assert_awaited_once()
        token_arg = mock_authentication_provider.validate_token.await_args.args[0]
        assert token_arg == "test-jwt-token"


class TestExcludedPaths:
    def test_health_endpoint_does_not_require_auth(self, client):
        response = client.get("/api/v1/health")
        assert response.status_code == 200

    def test_ready_endpoint_does_not_require_auth(self, client):
        response = client.get("/api/v1/ready")
        assert response.status_code in (200, 503)
