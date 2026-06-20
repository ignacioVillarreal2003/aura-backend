"""
Tests for:
  GET /api/v1/document-query/manage/document/{id}
  GET /api/v1/document-query/manage/document/{id}/status
  GET /api/v1/document-query/manage/documents
  GET /api/v1/document-query/document/{id}/status
  GET /api/v1/document-query/documents/chat/{id}
"""
from datetime import datetime, timezone

from app.domain.dtos.document.document_query.document_list_response import DocumentListResponse
from app.domain.dtos.document.document_query.document_response import DocumentResponse
from app.domain.dtos.document.document_query.document_status_response import DocumentStatusResponse

DOC_URL = "/api/v1/document-query/manage/document/1"
STATUS_URL = "/api/v1/document-query/manage/document/1/status"
USER_STATUS_URL = "/api/v1/document-query/document/1/status"
LIST_URL = "/api/v1/document-query/manage/documents"
CHAT_URL = "/api/v1/document-query/documents/chat/5"

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

_STATUS = DocumentStatusResponse(
    id=1,
    status="processed",
    enrichment_status="processed",
    graph_status="pending",
    processing_started_at=_NOW,
)

_LIST = DocumentListResponse(documents=[_DOC])


class TestDocumentQueryAuth:
    def test_missing_auth_document_returns_401(self, client):
        assert client.get(DOC_URL).status_code == 401

    def test_missing_auth_list_returns_401(self, client):
        assert client.get(LIST_URL).status_code == 401

    def test_missing_auth_chat_returns_401(self, client):
        assert client.get(CHAT_URL).status_code == 401

    def test_missing_auth_status_returns_401(self, client):
        assert client.get(STATUS_URL).status_code == 401

    def test_status_without_permission_returns_403(self, client, service_headers, mock_document_query_service):
        headers = service_headers(permissions=["DOCUMENT_QUERY"])
        assert client.get(STATUS_URL, headers=headers).status_code == 403

    def test_missing_auth_user_status_returns_401(self, client):
        assert client.get(USER_STATUS_URL).status_code == 401

    def test_user_status_without_permission_returns_403(self, client, service_headers, mock_document_query_service):
        headers = service_headers(permissions=["DOCUMENT_QUERY_MANAGE"])
        assert client.get(USER_STATUS_URL, headers=headers).status_code == 403


class TestDocumentQueryValidation:
    def test_page_size_above_max_returns_422(self, client, auth_headers, mock_document_query_service):
        response = client.get(LIST_URL, params={"size": 101}, headers=auth_headers)
        assert response.status_code == 422

    def test_page_zero_returns_422(self, client, auth_headers, mock_document_query_service):
        response = client.get(LIST_URL, params={"page": 0}, headers=auth_headers)
        assert response.status_code == 422

    def test_invalid_document_type_returns_422(self, client, auth_headers, mock_document_query_service):
        response = client.get(LIST_URL, params={"document_type": "invalid_type"}, headers=auth_headers)
        assert response.status_code == 422


class TestDocumentQuerySuccess:
    def test_get_document_returns_200(self, client, auth_headers, mock_document_query_service):
        mock_document_query_service.get_document_manage.return_value = _DOC
        assert client.get(DOC_URL, headers=auth_headers).status_code == 200

    def test_get_document_response_has_id_and_name(self, client, auth_headers, mock_document_query_service):
        mock_document_query_service.get_document_manage.return_value = _DOC
        body = client.get(DOC_URL, headers=auth_headers).json()
        assert body["id"] == 1
        assert body["name"] == "contrato.pdf"

    def test_get_status_returns_200(self, client, auth_headers, mock_document_query_service):
        mock_document_query_service.get_document_status_manage.return_value = _STATUS
        assert client.get(STATUS_URL, headers=auth_headers).status_code == 200

    def test_get_status_response_shape(self, client, auth_headers, mock_document_query_service):
        mock_document_query_service.get_document_status_manage.return_value = _STATUS
        body = client.get(STATUS_URL, headers=auth_headers).json()
        assert body["id"] == 1
        assert body["status"] == "processed"
        assert body["graph_status"] == "pending"
        assert "name" not in body

    def test_get_user_status_returns_200(self, client, auth_headers, mock_document_query_service):
        mock_document_query_service.get_document_status.return_value = _STATUS
        assert client.get(USER_STATUS_URL, headers=auth_headers).status_code == 200

    def test_get_user_status_response_shape(self, client, auth_headers, mock_document_query_service):
        mock_document_query_service.get_document_status.return_value = _STATUS
        body = client.get(USER_STATUS_URL, headers=auth_headers).json()
        assert body["id"] == 1
        assert body["status"] == "processed"
        assert "name" not in body

    def test_list_documents_returns_200(self, client, auth_headers, mock_document_query_service):
        mock_document_query_service.get_documents_manage.return_value = _LIST
        assert client.get(LIST_URL, headers=auth_headers).status_code == 200

    def test_list_documents_response_has_documents_key(self, client, auth_headers, mock_document_query_service):
        mock_document_query_service.get_documents_manage.return_value = _LIST
        body = client.get(LIST_URL, headers=auth_headers).json()
        assert "documents" in body
        assert isinstance(body["documents"], list)

    def test_list_by_chat_returns_200(self, client, auth_headers, mock_document_query_service):
        mock_document_query_service.get_documents_by_chat.return_value = _LIST
        assert client.get(CHAT_URL, headers=auth_headers).status_code == 200

    def test_list_accepts_optional_filters(self, client, auth_headers, mock_document_query_service):
        mock_document_query_service.get_documents_manage.return_value = _LIST
        response = client.get(
            LIST_URL,
            params={"page": 1, "size": 10, "document_type": "manual"},
            headers=auth_headers,
        )
        assert response.status_code == 200

    def test_document_service_unavailable_returns_503(self, client, auth_headers, app):
        original = getattr(app.state, "document_query_service", None)
        try:
            if hasattr(app.state, "document_query_service"):
                delattr(app.state, "document_query_service")
            assert client.get(DOC_URL, headers=auth_headers).status_code == 503
        finally:
            if original is not None:
                app.state.document_query_service = original
