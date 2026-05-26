"""
Tests for:
  POST   /api/v1/post-process-fragment/start
  POST   /api/v1/post-process-fragment/documents
  GET    /api/v1/post-process-fragment/status
  DELETE /api/v1/post-process-fragment/stop
"""
from app.domain.dtos.fragment.post_process_fragment.post_process_fragments_start_response import (
    PostProcessFragmentsStartResponse,
)
from app.domain.dtos.fragment.post_process_fragment.post_process_fragments_status_response import (
    PostProcessFragmentsStatusResponse,
)

START_ALL_URL = "/api/v1/post-process-fragment/start"
START_DOCS_URL = "/api/v1/post-process-fragment/documents"
STATUS_URL = "/api/v1/post-process-fragment/status"
STOP_URL = "/api/v1/post-process-fragment/stop"

_START_RESPONSE = PostProcessFragmentsStartResponse(
    message="Fragment post-process started",
    total_fragments=20,
    job_id="job-frag-xyz",
)

_STATUS_RESPONSE = PostProcessFragmentsStatusResponse(
    job_id="job-frag-xyz",
    is_running=False,
    total_fragments=20,
    processed_fragments=20,
    failed_fragments=0,
)


class TestPostProcessFragmentAuth:
    def test_start_all_missing_auth_returns_401(self, client):
        assert client.post(START_ALL_URL).status_code == 401

    def test_start_docs_missing_auth_returns_401(self, client):
        assert client.post(START_DOCS_URL, json={"document_ids": [1]}).status_code == 401

    def test_status_missing_auth_returns_401(self, client):
        assert client.get(STATUS_URL).status_code == 401

    def test_stop_missing_auth_returns_401(self, client):
        assert client.delete(STOP_URL).status_code == 401


class TestPostProcessFragmentValidation:
    def test_empty_document_ids_returns_422(self, client, auth_headers, mock_post_process_fragment_service):
        response = client.post(START_DOCS_URL, json={"document_ids": []}, headers=auth_headers)
        assert response.status_code == 422

    def test_duplicate_document_ids_returns_422(self, client, auth_headers, mock_post_process_fragment_service):
        response = client.post(START_DOCS_URL, json={"document_ids": [1, 1]}, headers=auth_headers)
        assert response.status_code == 422

    def test_zero_document_id_returns_422(self, client, auth_headers, mock_post_process_fragment_service):
        response = client.post(START_DOCS_URL, json={"document_ids": [0]}, headers=auth_headers)
        assert response.status_code == 422

    def test_missing_document_ids_returns_422(self, client, auth_headers, mock_post_process_fragment_service):
        response = client.post(START_DOCS_URL, json={}, headers=auth_headers)
        assert response.status_code == 422


class TestPostProcessFragmentSuccess:
    def test_start_all_returns_202(self, client, auth_headers, mock_post_process_fragment_service):
        mock_post_process_fragment_service.start_all.return_value = _START_RESPONSE
        assert client.post(START_ALL_URL, headers=auth_headers).status_code == 202

    def test_start_all_response_has_message_and_total(self, client, auth_headers, mock_post_process_fragment_service):
        mock_post_process_fragment_service.start_all.return_value = _START_RESPONSE
        body = client.post(START_ALL_URL, headers=auth_headers).json()
        assert "message" in body
        assert "total_fragments" in body

    def test_start_for_documents_returns_202(self, client, auth_headers, mock_post_process_fragment_service):
        mock_post_process_fragment_service.start_for_documents.return_value = _START_RESPONSE
        response = client.post(START_DOCS_URL, json={"document_ids": [1, 2]}, headers=auth_headers)
        assert response.status_code == 202

    def test_status_returns_200(self, client, auth_headers, mock_post_process_fragment_service):
        mock_post_process_fragment_service.get_status.return_value = _STATUS_RESPONSE
        assert client.get(STATUS_URL, headers=auth_headers).status_code == 200

    def test_status_response_has_is_running(self, client, auth_headers, mock_post_process_fragment_service):
        mock_post_process_fragment_service.get_status.return_value = _STATUS_RESPONSE
        body = client.get(STATUS_URL, headers=auth_headers).json()
        assert "is_running" in body
        assert "total_fragments" in body

    def test_stop_returns_204(self, client, auth_headers, mock_post_process_fragment_service):
        mock_post_process_fragment_service.stop.return_value = None
        assert client.delete(STOP_URL, headers=auth_headers).status_code == 204

    def test_service_unavailable_returns_503(self, client, auth_headers, app):
        original = getattr(app.state, "post_process_fragment_service", None)
        try:
            if hasattr(app.state, "post_process_fragment_service"):
                delattr(app.state, "post_process_fragment_service")
            assert client.post(START_ALL_URL, headers=auth_headers).status_code == 503
        finally:
            if original is not None:
                app.state.post_process_fragment_service = original
