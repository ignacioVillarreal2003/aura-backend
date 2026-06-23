"""
Tests for POST /api/v1/document-summary
"""
from app.domain.dtos.user_interactions.document_summary.document_summary_response import DocumentSummaryResponse

URL = "/api/v1/document-summary"

VALID_BODY = {"document_ids": [1, 2, 3], "chat_id": 1}

_RESPONSE = DocumentSummaryResponse(
    title="Resumen de documentos",
    description="Síntesis introductoria de los documentos solicitados.",
    summary="Resumen consolidado de los tres documentos solicitados.",
    fragments=[],
)


class TestDocumentSummaryAuth:
    def test_missing_auth_returns_401(self, client):
        response = client.post(URL, json=VALID_BODY)
        assert response.status_code == 401

    def test_missing_permission_returns_403(self, client, make_auth_headers, mock_document_summary_service):
        response = client.post(URL, json=VALID_BODY, headers=make_auth_headers(permissions=[]))
        assert response.status_code == 403

    def test_wrong_permission_returns_403(self, client, make_auth_headers, mock_document_summary_service):
        response = client.post(URL, json=VALID_BODY, headers=make_auth_headers(permissions=["LLM_AGENT"]))
        assert response.status_code == 403


class TestDocumentSummaryValidation:
    def test_empty_document_ids_returns_422(self, client, auth_headers, mock_document_summary_service):
        response = client.post(URL, json={"document_ids": []}, headers=auth_headers)
        assert response.status_code == 422

    def test_duplicate_document_ids_returns_422(self, client, auth_headers, mock_document_summary_service):
        response = client.post(URL, json={"document_ids": [1, 1, 2]}, headers=auth_headers)
        assert response.status_code == 422

    def test_zero_document_id_returns_422(self, client, auth_headers, mock_document_summary_service):
        response = client.post(URL, json={"document_ids": [0]}, headers=auth_headers)
        assert response.status_code == 422

    def test_missing_document_ids_field_returns_422(self, client, auth_headers, mock_document_summary_service):
        response = client.post(URL, json={}, headers=auth_headers)
        assert response.status_code == 422

    def test_too_many_document_ids_returns_422(self, client, auth_headers, mock_document_summary_service):
        response = client.post(URL, json={"document_ids": list(range(1, 52))}, headers=auth_headers)
        assert response.status_code == 422


class TestDocumentSummarySuccess:
    def test_valid_request_returns_200(self, client, auth_headers, mock_document_summary_service):
        mock_document_summary_service.execute_document_summary.return_value = _RESPONSE
        response = client.post(URL, json=VALID_BODY, headers=auth_headers)
        assert response.status_code == 200

    def test_response_has_summary_field(self, client, auth_headers, mock_document_summary_service):
        mock_document_summary_service.execute_document_summary.return_value = _RESPONSE
        body = client.post(URL, json=VALID_BODY, headers=auth_headers).json()
        assert "summary" in body

    def test_service_unavailable_returns_503(self, client, auth_headers, app):
        original = getattr(app.state, "document_summary_service", None)
        try:
            if hasattr(app.state, "document_summary_service"):
                delattr(app.state, "document_summary_service")
            response = client.post(URL, json=VALID_BODY, headers=auth_headers)
            assert response.status_code == 503
        finally:
            if original is not None:
                app.state.document_summary_service = original
