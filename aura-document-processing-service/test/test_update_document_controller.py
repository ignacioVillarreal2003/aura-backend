"""
Tests for PATCH /api/v1/update-document/manage/document/{id}
"""
from datetime import datetime, timezone

from app.domain.dtos.document.document_query.document_response import DocumentResponse

URL = "/api/v1/update-document/manage/document/1"

_NOW = datetime(2025, 1, 1, tzinfo=timezone.utc)

_DOC = DocumentResponse(
    id=1,
    name="nuevo-nombre.pdf",
    description="nueva descripción",
    mime_type="application/pdf",
    status="processed",
    file_size_bytes=1024,
    category="contratos",
    created_by=42,
    created_at=_NOW,
    updated_by=42,
    updated_at=_NOW,
)


class TestUpdateDocumentAuth:
    def test_missing_auth_returns_401(self, client):
        assert client.patch(URL, json={"name": "x"}).status_code == 401

    def test_without_permission_returns_403(self, client, service_headers, mock_update_document_service):
        headers = service_headers(permissions=["GET_DOCUMENT"])
        assert client.patch(URL, json={"name": "x"}, headers=headers).status_code == 403


class TestUpdateDocumentValidation:
    def test_empty_body_returns_422(self, client, auth_headers, mock_update_document_service):
        assert client.patch(URL, json={}, headers=auth_headers).status_code == 422

    def test_unknown_field_returns_422(self, client, auth_headers, mock_update_document_service):
        response = client.patch(URL, json={"status": "processed"}, headers=auth_headers)
        assert response.status_code == 422

    def test_blank_name_returns_422(self, client, auth_headers, mock_update_document_service):
        assert client.patch(URL, json={"name": "   "}, headers=auth_headers).status_code == 422


class TestUpdateDocumentSuccess:
    def test_update_returns_200(self, client, auth_headers, mock_update_document_service):
        mock_update_document_service.update_document_manage.return_value = _DOC
        response = client.patch(URL, json={"name": "nuevo-nombre.pdf"}, headers=auth_headers)
        assert response.status_code == 200

    def test_update_response_has_updated_name(self, client, auth_headers, mock_update_document_service):
        mock_update_document_service.update_document_manage.return_value = _DOC
        body = client.patch(
            URL,
            json={"name": "nuevo-nombre.pdf"},
            headers=auth_headers,
        ).json()
        assert body["name"] == "nuevo-nombre.pdf"

    def test_description_is_not_editable(self, client, auth_headers, mock_update_document_service):
        response = client.patch(URL, json={"name": "x", "description": "manual"}, headers=auth_headers)
        assert response.status_code == 422

    def test_category_is_not_editable(self, client, auth_headers, mock_update_document_service):
        response = client.patch(URL, json={"name": "x", "category": "contratos"}, headers=auth_headers)
        assert response.status_code == 422

    def test_service_unavailable_returns_503(self, client, auth_headers, app):
        original = getattr(app.state, "update_document_service", None)
        try:
            if hasattr(app.state, "update_document_service"):
                delattr(app.state, "update_document_service")
            assert client.patch(URL, json={"name": "x"}, headers=auth_headers).status_code == 503
        finally:
            if original is not None:
                app.state.update_document_service = original
