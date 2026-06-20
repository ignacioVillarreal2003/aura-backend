"""
Tests for DELETE /api/v1/delete-document/soft/document/{id}
         DELETE /api/v1/delete-document/soft/chat/{id}
         DELETE /api/v1/delete-document/manage/soft/document/{id}
"""

DOC_URL = "/api/v1/delete-document/soft/document/1"
CHAT_URL = "/api/v1/delete-document/soft/chat/5"
ADMIN_DOC_URL = "/api/v1/delete-document/manage/soft/document/1"


class TestDeleteDocumentAuth:
    def test_missing_auth_document_returns_401(self, client):
        assert client.delete(DOC_URL).status_code == 401

    def test_missing_auth_chat_returns_401(self, client):
        assert client.delete(CHAT_URL).status_code == 401

    def test_missing_auth_admin_document_returns_401(self, client):
        assert client.delete(ADMIN_DOC_URL).status_code == 401

    def test_admin_document_without_permission_returns_403(
            self, client, service_headers, mock_delete_document_service
    ):
        headers = service_headers(permissions=["DOCUMENT_DELETE"])
        assert client.delete(ADMIN_DOC_URL, headers=headers).status_code == 403


class TestDeleteDocumentSuccess:
    def test_soft_delete_document_returns_204(self, client, auth_headers, mock_delete_document_service):
        mock_delete_document_service.soft_delete_document.return_value = None
        response = client.delete(DOC_URL, headers=auth_headers)
        assert response.status_code == 204

    def test_soft_delete_document_has_no_body(self, client, auth_headers, mock_delete_document_service):
        mock_delete_document_service.soft_delete_document.return_value = None
        response = client.delete(DOC_URL, headers=auth_headers)
        assert response.content == b""

    def test_soft_delete_chat_returns_204(self, client, auth_headers, mock_delete_document_service):
        mock_delete_document_service.soft_delete_documents_by_chat.return_value = None
        response = client.delete(CHAT_URL, headers=auth_headers)
        assert response.status_code == 204

    def test_soft_delete_document_admin_returns_204(self, client, auth_headers, mock_delete_document_service):
        mock_delete_document_service.soft_delete_document_manage.return_value = None
        response = client.delete(ADMIN_DOC_URL, headers=auth_headers)
        assert response.status_code == 204

    def test_soft_delete_document_admin_has_no_body(self, client, auth_headers, mock_delete_document_service):
        mock_delete_document_service.soft_delete_document_manage.return_value = None
        response = client.delete(ADMIN_DOC_URL, headers=auth_headers)
        assert response.content == b""

    def test_service_unavailable_admin_document_returns_503(self, client, auth_headers, app):
        original = getattr(app.state, "delete_document_service", None)
        try:
            if hasattr(app.state, "delete_document_service"):
                delattr(app.state, "delete_document_service")
            assert client.delete(ADMIN_DOC_URL, headers=auth_headers).status_code == 503
        finally:
            if original is not None:
                app.state.delete_document_service = original

    def test_service_unavailable_document_returns_503(self, client, auth_headers, app):
        original = getattr(app.state, "delete_document_service", None)
        try:
            if hasattr(app.state, "delete_document_service"):
                delattr(app.state, "delete_document_service")
            assert client.delete(DOC_URL, headers=auth_headers).status_code == 503
        finally:
            if original is not None:
                app.state.delete_document_service = original

    def test_service_unavailable_chat_returns_503(self, client, auth_headers, app):
        original = getattr(app.state, "delete_document_service", None)
        try:
            if hasattr(app.state, "delete_document_service"):
                delattr(app.state, "delete_document_service")
            assert client.delete(CHAT_URL, headers=auth_headers).status_code == 503
        finally:
            if original is not None:
                app.state.delete_document_service = original
