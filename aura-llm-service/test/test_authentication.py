"""
Tests for the AuthenticationProviderMiddleware behaviour on protected routes.
Uses /api/v1/document-classify as a representative protected endpoint.
"""
from app.configuration.environment_variables import environment_variables

PROTECTED_URL = "/api/v1/document-classify"

VALID_BODY = {
    "document_name": "contrato_001.pdf",
    "content": "Este es el contenido del documento de prueba.",
}


class TestServiceToServiceAuth:
    def test_missing_all_headers_returns_401(self, client):
        response = client.post(PROTECTED_URL, json=VALID_BODY)
        assert response.status_code == 401

    def test_wrong_api_key_returns_403(self, client):
        headers = {
            "X-Service-Api-Key": "wrong-key",
            "X-User-Id": "42",
            "X-User-Email": "user@test.com",
        }
        response = client.post(PROTECTED_URL, json=VALID_BODY, headers=headers)
        assert response.status_code == 403

    def test_empty_api_key_returns_401(self, client):
        headers = {
            "X-Service-Api-Key": "   ",
            "X-User-Id": "42",
            "X-User-Email": "user@test.com",
        }
        response = client.post(PROTECTED_URL, json=VALID_BODY, headers=headers)
        assert response.status_code == 401

    def test_missing_user_id_returns_400(self, client):
        headers = {
            "X-Service-Api-Key": environment_variables.service_api_key,
            "X-User-Email": "user@test.com",
        }
        response = client.post(PROTECTED_URL, json=VALID_BODY, headers=headers)
        assert response.status_code == 400

    def test_non_integer_user_id_returns_400(self, client):
        headers = {
            "X-Service-Api-Key": environment_variables.service_api_key,
            "X-User-Id": "not-an-integer",
            "X-User-Email": "user@test.com",
        }
        response = client.post(PROTECTED_URL, json=VALID_BODY, headers=headers)
        assert response.status_code == 400

    def test_missing_user_email_returns_400(self, client):
        headers = {
            "X-Service-Api-Key": environment_variables.service_api_key,
            "X-User-Id": "42",
        }
        response = client.post(PROTECTED_URL, json=VALID_BODY, headers=headers)
        assert response.status_code == 400

    def test_valid_service_auth_passes_middleware(self, client, mock_document_classify_service):
        from app.domain.constants.document_type import DocumentType
        from app.domain.dtos.processing.document_classify.classify_document_response import ClassifyDocumentResponse

        mock_document_classify_service.classify_document.return_value = ClassifyDocumentResponse(
            type=DocumentType.informe,
            category="Legal",
            description="Documento legal de prueba.",
        )
        headers = {
            "X-Service-Api-Key": environment_variables.service_api_key,
            "X-User-Id": "42",
            "X-User-Email": "user@test.com",
            "X-User-Permissions": "LLM_DOCUMENT_CLASSIFY",
        }
        response = client.post(PROTECTED_URL, json=VALID_BODY, headers=headers)
        assert response.status_code != 401
        assert response.status_code != 403

    def test_health_endpoint_does_not_require_auth(self, client):
        response = client.get("/api/v1/health")
        assert response.status_code == 200

    def test_ready_endpoint_does_not_require_auth(self, client):
        response = client.get("/api/v1/ready")
        assert response.status_code in (200, 503)

    def test_missing_bearer_token_on_protected_route_returns_401(self, client):
        # No service key and no Bearer → 401
        response = client.post(PROTECTED_URL, json=VALID_BODY)
        assert response.status_code == 401
        body = response.json()
        assert "error" in body
