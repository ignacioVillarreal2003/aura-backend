"""
Tests for POST /api/v1/document-action
"""
from app.domain.dtos.user_interactions.document_action.document_action_response import DocumentActionResponse

URL = "/api/v1/document-action"

VALID_BODY = {
    "document_ids": [1, 2],
    "instruction": "Extraer las fechas importantes mencionadas en el documento.",
    "chat_id": 1,
}

_RESPONSE = DocumentActionResponse(
    title="Fechas importantes del documento",
    description="Listado de las fechas relevantes mencionadas.",
    result="Las fechas encontradas son: 01/01/2024 y 15/06/2024.",
    instruction="Extraer las fechas importantes mencionadas en el documento.",
    action=None,
)


class TestDocumentActionAuth:
    def test_missing_auth_returns_401(self, client):
        response = client.post(URL, json=VALID_BODY)
        assert response.status_code == 401

    def test_missing_permission_returns_403(self, client, make_auth_headers, mock_document_action_service):
        response = client.post(URL, json=VALID_BODY, headers=make_auth_headers(permissions=[]))
        assert response.status_code == 403

    def test_wrong_permission_returns_403(self, client, make_auth_headers, mock_document_action_service):
        response = client.post(URL, json=VALID_BODY, headers=make_auth_headers(permissions=["LLM_AGENT"]))
        assert response.status_code == 403


class TestDocumentActionValidation:
    def test_empty_document_ids_returns_422(self, client, auth_headers, mock_document_action_service):
        response = client.post(URL, json={"document_ids": [], "instruction": "Resumir."}, headers=auth_headers)
        assert response.status_code == 422

    def test_blank_instruction_returns_422(self, client, auth_headers, mock_document_action_service):
        response = client.post(URL, json={"document_ids": [1], "instruction": "  "}, headers=auth_headers)
        assert response.status_code == 422

    def test_duplicate_ids_returns_422(self, client, auth_headers, mock_document_action_service):
        response = client.post(URL, json={"document_ids": [1, 1], "instruction": "Resumir."}, headers=auth_headers)
        assert response.status_code == 422

    def test_missing_instruction_returns_422(self, client, auth_headers, mock_document_action_service):
        response = client.post(URL, json={"document_ids": [1]}, headers=auth_headers)
        assert response.status_code == 422


class TestDocumentActionSuccess:
    def test_valid_request_returns_200(self, client, auth_headers, mock_document_action_service):
        mock_document_action_service.execute_document_action.return_value = _RESPONSE
        response = client.post(URL, json=VALID_BODY, headers=auth_headers)
        assert response.status_code == 200

    def test_response_has_result_field(self, client, auth_headers, mock_document_action_service):
        mock_document_action_service.execute_document_action.return_value = _RESPONSE
        body = client.post(URL, json=VALID_BODY, headers=auth_headers).json()
        assert "result" in body

    def test_service_called_with_correct_instruction(self, client, auth_headers, mock_document_action_service):
        mock_document_action_service.execute_document_action.return_value = _RESPONSE
        client.post(URL, json=VALID_BODY, headers=auth_headers)
        call_kwargs = mock_document_action_service.execute_document_action.call_args[1]
        assert call_kwargs["document_action_request"].instruction == VALID_BODY["instruction"]

    def test_service_unavailable_returns_503(self, client, auth_headers, app):
        original = getattr(app.state, "document_action_service", None)
        try:
            if hasattr(app.state, "document_action_service"):
                delattr(app.state, "document_action_service")
            response = client.post(URL, json=VALID_BODY, headers=auth_headers)
            assert response.status_code == 503
        finally:
            if original is not None:
                app.state.document_action_service = original
