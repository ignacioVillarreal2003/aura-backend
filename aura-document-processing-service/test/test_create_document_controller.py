"""
Tests for POST /api/v1/create-document
"""
from app.domain.dtos.document.create_document.create_document_response import CreateDocumentResponse

URL = "/api/v1/create-document"

_VALID_FILE = ("test.pdf", b"%PDF-1.4 test content", "application/pdf")

_RESPONSE = CreateDocumentResponse(
    id=1,
    name="test.pdf",
    mime_type="application/pdf",
    status="uploaded",
    file_size_bytes=21,
)


class TestCreateDocumentAuth:
    def test_missing_auth_returns_401(self, client):
        response = client.post(URL, files={"file": _VALID_FILE})
        assert response.status_code == 401


class TestCreateDocumentValidation:
    def test_missing_file_returns_422(self, client, auth_headers, mock_create_document_service):
        response = client.post(URL, headers=auth_headers)
        assert response.status_code == 422


class TestCreateDocumentSuccess:
    def test_valid_request_returns_201(self, client, auth_headers, mock_create_document_service):
        mock_create_document_service.create_document.return_value = _RESPONSE
        response = client.post(
            URL,
            files={"file": _VALID_FILE},
            headers=auth_headers,
        )
        assert response.status_code == 201

    def test_response_has_expected_fields(self, client, auth_headers, mock_create_document_service):
        mock_create_document_service.create_document.return_value = _RESPONSE
        body = client.post(URL, files={"file": _VALID_FILE}, headers=auth_headers).json()
        assert "id" in body
        assert "name" in body
        assert "mime_type" in body
        assert "status" in body
        assert "file_size_bytes" in body

    def test_prefer_docling_form_field_accepted(self, client, auth_headers, mock_create_document_service):
        mock_create_document_service.create_document.return_value = _RESPONSE
        response = client.post(
            URL,
            files={"file": _VALID_FILE},
            data={"prefer_docling": "true"},
            headers=auth_headers,
        )
        assert response.status_code == 201

    def test_service_unavailable_returns_503(self, client, auth_headers, app):
        original = getattr(app.state, "create_document_service", None)
        try:
            if hasattr(app.state, "create_document_service"):
                delattr(app.state, "create_document_service")
            response = client.post(URL, files={"file": _VALID_FILE}, headers=auth_headers)
            assert response.status_code == 503
        finally:
            if original is not None:
                app.state.create_document_service = original
