"""
Tests for the bulk re-embed endpoints:
  POST   /api/v1/document-reembed/manage
  GET    /api/v1/document-reembed/manage/status
  DELETE /api/v1/document-reembed/manage/stop
"""
from app.domain.constants.document.bulk_operation import BulkOperation
from app.domain.dtos.document.bulk.bulk_responses import BulkJobStatusResponse, BulkStartResponse

URL = "/api/v1/document-reembed/manage"

_START = BulkStartResponse(job_id="abc123", operation=BulkOperation.reembed, total=3, queued=True)
_STATUS = BulkJobStatusResponse(
    job_id="abc123", operation=BulkOperation.reembed, is_running=True,
    total=3, processed=1, failed=0,
)


class TestReembedAuth:
    def test_missing_auth_returns_401(self, client):
        assert client.post(URL, json={"selector": {"document_ids": [1]}}).status_code == 401


class TestReembedValidation:
    def test_both_selector_modes_returns_422(self, client, auth_headers, mock_bulk_dispatch_service):
        body = {"selector": {"document_ids": [1], "all_documents": True}}
        assert client.post(URL, json=body, headers=auth_headers).status_code == 422

    def test_no_selector_mode_returns_422(self, client, auth_headers, mock_bulk_dispatch_service):
        assert client.post(URL, json={"selector": {}}, headers=auth_headers).status_code == 422


class TestReembedSuccess:
    def test_single_id_returns_202(self, client, auth_headers, mock_bulk_dispatch_service):
        mock_bulk_dispatch_service.start.return_value = _START
        body = {"selector": {"document_ids": [1]}}
        response = client.post(URL, json=body, headers=auth_headers)
        assert response.status_code == 202
        assert response.json()["job_id"] == "abc123"

    def test_all_documents_returns_202(self, client, auth_headers, mock_bulk_dispatch_service):
        mock_bulk_dispatch_service.start.return_value = _START
        body = {"selector": {"all_documents": True}}
        response = client.post(URL, json=body, headers=auth_headers)
        assert response.status_code == 202
        assert mock_bulk_dispatch_service.start.await_args.kwargs["operation"] == BulkOperation.reembed

    def test_status_returns_200(self, client, auth_headers, mock_bulk_dispatch_service):
        mock_bulk_dispatch_service.status.return_value = _STATUS
        response = client.get(f"{URL}/status", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["processed"] == 1

    def test_stop_returns_200(self, client, auth_headers, mock_bulk_dispatch_service):
        mock_bulk_dispatch_service.stop.return_value = _STATUS
        response = client.request("DELETE", f"{URL}/stop", headers=auth_headers)
        assert response.status_code == 200
        mock_bulk_dispatch_service.stop.assert_awaited_once()
