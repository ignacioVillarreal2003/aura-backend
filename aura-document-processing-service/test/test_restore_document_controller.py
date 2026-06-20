"""
Tests for POST /api/v1/restore-document/manage/document/{id}
"""
from datetime import datetime, timezone

from app.domain.dtos.document.document_query.document_response import DocumentResponse

URL = "/api/v1/restore-document/manage/document/1"

_NOW = datetime(2025, 1, 1, tzinfo=timezone.utc)

_DOC = DocumentResponse(
    id=1,
    name="contrato.pdf",
    mime_type="application/pdf",
    status="processed",
    file_size_bytes=1024,
    created_by=42,
    created_at=_NOW,
)


class TestRestoreDocumentAuth:
    def test_missing_auth_returns_401(self, client):
        assert client.post(URL).status_code == 401

    def test_without_permission_returns_403(self, client, service_headers, mock_restore_document_service):
        headers = service_headers(permissions=["DOCUMENT_QUERY_MANAGE"])
        assert client.post(URL, headers=headers).status_code == 403


class TestRestoreDocumentSuccess:
    def test_restore_document_returns_200(self, client, auth_headers, mock_restore_document_service):
        mock_restore_document_service.restore_document_manage.return_value = _DOC
        response = client.post(URL, headers=auth_headers)
        assert response.status_code == 200

    def test_restore_document_response_has_id(self, client, auth_headers, mock_restore_document_service):
        mock_restore_document_service.restore_document_manage.return_value = _DOC
        body = client.post(URL, headers=auth_headers).json()
        assert body["id"] == 1

    def test_service_unavailable_returns_503(self, client, auth_headers, app):
        original = getattr(app.state, "restore_document_service", None)
        try:
            if hasattr(app.state, "restore_document_service"):
                delattr(app.state, "restore_document_service")
            assert client.post(URL, headers=auth_headers).status_code == 503
        finally:
            if original is not None:
                app.state.restore_document_service = original
