"""
Tests for POST /api/v1/document-classify
"""
from app.domain.constants.document_type import DocumentType
from app.domain.dtos.processing.document_classify.classify_document_response import ClassifyDocumentResponse

URL = "/api/v1/document-classify"

VALID_BODY = {
    "document_name": "contrato_001.pdf",
    "content": "Texto de contenido del documento de prueba para clasificación.",
}

_RESPONSE = ClassifyDocumentResponse(
    type=DocumentType.informe,
    category="Legal",
    description="Documento de tipo informe sobre cuestiones legales.",
)


class TestDocumentClassifyAuth:
    def test_missing_auth_returns_401(self, client):
        response = client.post(URL, json=VALID_BODY)
        assert response.status_code == 401

    def test_missing_permission_returns_403(self, client, make_auth_headers, mock_document_classify_service):
        response = client.post(URL, json=VALID_BODY, headers=make_auth_headers(permissions=[]))
        assert response.status_code == 403

    def test_wrong_permission_returns_403(self, client, make_auth_headers, mock_document_classify_service):
        response = client.post(URL, json=VALID_BODY, headers=make_auth_headers(permissions=["LLM_AGENT"]))
        assert response.status_code == 403


class TestDocumentClassifyValidation:
    def test_missing_document_name_returns_422(self, client, auth_headers, mock_document_classify_service):
        response = client.post(URL, json={"content": "Texto."}, headers=auth_headers)
        assert response.status_code == 422

    def test_missing_content_returns_422(self, client, auth_headers, mock_document_classify_service):
        response = client.post(URL, json={"document_name": "doc.pdf"}, headers=auth_headers)
        assert response.status_code == 422

    def test_blank_document_name_returns_422(self, client, auth_headers, mock_document_classify_service):
        response = client.post(URL, json={"document_name": "  ", "content": "Texto."}, headers=auth_headers)
        assert response.status_code == 422

    def test_blank_content_returns_422(self, client, auth_headers, mock_document_classify_service):
        response = client.post(URL, json={"document_name": "doc.pdf", "content": "  "}, headers=auth_headers)
        assert response.status_code == 422

    def test_empty_body_returns_422(self, client, auth_headers, mock_document_classify_service):
        response = client.post(URL, json={}, headers=auth_headers)
        assert response.status_code == 422


class TestDocumentClassifySuccess:
    def test_valid_request_calls_service_and_returns_200(self, client, auth_headers, mock_document_classify_service):
        mock_document_classify_service.classify_document.return_value = _RESPONSE
        response = client.post(URL, json=VALID_BODY, headers=auth_headers)
        assert response.status_code == 200

    def test_response_contains_type_field(self, client, auth_headers, mock_document_classify_service):
        mock_document_classify_service.classify_document.return_value = _RESPONSE
        body = client.post(URL, json=VALID_BODY, headers=auth_headers).json()
        assert "type" in body

    def test_response_contains_category_and_description(self, client, auth_headers, mock_document_classify_service):
        mock_document_classify_service.classify_document.return_value = _RESPONSE
        body = client.post(URL, json=VALID_BODY, headers=auth_headers).json()
        assert "category" in body
        assert "description" in body

    def test_service_called_with_request_data(self, client, auth_headers, mock_document_classify_service):
        mock_document_classify_service.classify_document.return_value = _RESPONSE
        client.post(URL, json=VALID_BODY, headers=auth_headers)
        assert mock_document_classify_service.classify_document.called
        call_kwargs = mock_document_classify_service.classify_document.call_args[1]
        assert call_kwargs["classify_document_request"].document_name == "contrato_001.pdf"

    def test_service_unavailable_returns_503(self, client, auth_headers, app):
        original = getattr(app.state, "document_classify_service", None)
        try:
            if hasattr(app.state, "document_classify_service"):
                delattr(app.state, "document_classify_service")
            response = client.post(URL, json=VALID_BODY, headers=auth_headers)
            assert response.status_code == 503
        finally:
            if original is not None:
                app.state.document_classify_service = original
