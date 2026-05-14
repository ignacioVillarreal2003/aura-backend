"""
Tests for:
  POST   /api/v1/post-process-document/start
  POST   /api/v1/post-process-document/documents
  GET    /api/v1/post-process-document/status
  DELETE /api/v1/post-process-document/stop
"""
from app.domain.dtos.document.post_process_document.post_process_documents_start_response import (
    PostProcessDocumentsStartResponse,
)
from app.domain.dtos.document.post_process_document.post_process_documents_status_response import (
    PostProcessDocumentsStatusResponse,
)

START_ALL_URL = "/api/v1/post-process-document/start"
START_DOCS_URL = "/api/v1/post-process-document/documents"
STATUS_URL = "/api/v1/post-process-document/status"
STOP_URL = "/api/v1/post-process-document/stop"

_START_RESPONSE = PostProcessDocumentsStartResponse(
    message="Post-process started",
    total_documents=5,
    job_id="job-abc123",
)

_STATUS_RESPONSE = PostProcessDocumentsStatusResponse(
    job_id="job-abc123",
    is_running=False,
    total_documents=5,
    processed_documents=5,
    failed_documents=0,
)


class TestPostProcessDocumentAuth:
    def test_start_all_missing_auth_returns_401(self, client):
        assert client.post(START_ALL_URL).status_code == 401

    def test_start_docs_missing_auth_returns_401(self, client):
        assert client.post(START_DOCS_URL, json={"document_ids": [1]}).status_code == 401

    def test_status_missing_auth_returns_401(self, client):
        assert client.get(STATUS_URL).status_code == 401

    def test_stop_missing_auth_returns_401(self, client):
        assert client.delete(STOP_URL).status_code == 401


class TestPostProcessDocumentValidation:
    def test_empty_document_ids_returns_422(self, client, auth_headers, mock_post_process_document_service):
        response = client.post(START_DOCS_URL, json={"document_ids": []}, headers=auth_headers)
        assert response.status_code == 422

    def test_duplicate_document_ids_returns_422(self, client, auth_headers, mock_post_process_document_service):
        response = client.post(START_DOCS_URL, json={"document_ids": [1, 1]}, headers=auth_headers)
        assert response.status_code == 422

    def test_zero_document_id_returns_422(self, client, auth_headers, mock_post_process_document_service):
        response = client.post(START_DOCS_URL, json={"document_ids": [0]}, headers=auth_headers)
        assert response.status_code == 422

    def test_missing_document_ids_returns_422(self, client, auth_headers, mock_post_process_document_service):
        response = client.post(START_DOCS_URL, json={}, headers=auth_headers)
        assert response.status_code == 422


class TestPostProcessDocumentSuccess:
    def test_start_all_returns_202(self, client, auth_headers, mock_post_process_document_service):
        mock_post_process_document_service.start_all.return_value = _START_RESPONSE
        assert client.post(START_ALL_URL, headers=auth_headers).status_code == 202

    def test_start_all_response_has_message(self, client, auth_headers, mock_post_process_document_service):
        mock_post_process_document_service.start_all.return_value = _START_RESPONSE
        body = client.post(START_ALL_URL, headers=auth_headers).json()
        assert "message" in body
        assert "total_documents" in body

    def test_start_for_documents_returns_202(self, client, auth_headers, mock_post_process_document_service):
        mock_post_process_document_service.start_for_documents.return_value = _START_RESPONSE
        response = client.post(START_DOCS_URL, json={"document_ids": [1, 2, 3]}, headers=auth_headers)
        assert response.status_code == 202

    def test_status_returns_200(self, client, auth_headers, mock_post_process_document_service):
        mock_post_process_document_service.get_status.return_value = _STATUS_RESPONSE
        assert client.get(STATUS_URL, headers=auth_headers).status_code == 200

    def test_status_response_has_is_running(self, client, auth_headers, mock_post_process_document_service):
        mock_post_process_document_service.get_status.return_value = _STATUS_RESPONSE
        body = client.get(STATUS_URL, headers=auth_headers).json()
        assert "is_running" in body
        assert "total_documents" in body

    def test_stop_returns_204(self, client, auth_headers, mock_post_process_document_service):
        mock_post_process_document_service.stop.return_value = None
        assert client.delete(STOP_URL, headers=auth_headers).status_code == 204

    def test_service_unavailable_returns_503(self, client, auth_headers, app):
        original = getattr(app.state, "post_process_document_service", None)
        try:
            if hasattr(app.state, "post_process_document_service"):
                delattr(app.state, "post_process_document_service")
            assert client.post(START_ALL_URL, headers=auth_headers).status_code == 503
        finally:
            if original is not None:
                app.state.post_process_document_service = original
