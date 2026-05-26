"""
Tests for GET /api/v1/document-download/document/{id}/download
"""

URL = "/api/v1/document-download/document/1/download"


async def _bytes_stream():
    yield b"fake pdf content"


class TestDocumentDownloadAuth:
    def test_missing_auth_returns_401(self, client):
        assert client.get(URL).status_code == 401


class TestDocumentDownloadSuccess:
    def test_valid_request_returns_200(self, client, auth_headers, mock_document_download_service):
        mock_document_download_service.download_document.return_value = (
            _bytes_stream(),
            "document.pdf",
            "application/pdf",
        )
        response = client.get(URL, headers=auth_headers)
        assert response.status_code == 200

    def test_response_has_content_disposition_header(self, client, auth_headers, mock_document_download_service):
        mock_document_download_service.download_document.return_value = (
            _bytes_stream(),
            "document.pdf",
            "application/pdf",
        )
        response = client.get(URL, headers=auth_headers)
        assert "content-disposition" in response.headers
        assert "document.pdf" in response.headers["content-disposition"]

    def test_service_unavailable_returns_503(self, client, auth_headers, app):
        original = getattr(app.state, "document_download_service", None)
        try:
            if hasattr(app.state, "document_download_service"):
                delattr(app.state, "document_download_service")
            assert client.get(URL, headers=auth_headers).status_code == 503
        finally:
            if original is not None:
                app.state.document_download_service = original
