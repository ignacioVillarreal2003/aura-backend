"""
Tests for POST /api/v1/document-question
"""
from app.domain.dtos.user_interactions.document_question.document_question_response import DocumentQuestionResponse
from app.domain.dtos.message import Message
from app.domain.constants.message_role import MessageRole

URL = "/api/v1/document-question"

VALID_BODY = {
    "messages": [{"role": "human", "content": "¿Qué dice el documento sobre contratos?"}],
    "chat_id": 1,
}

_RESPONSE = DocumentQuestionResponse(
    question="¿Qué dice el documento sobre contratos?",
    answer="El documento detalla los términos contractuales.",
    messages=[Message(role=MessageRole.human, content="¿Qué dice el documento sobre contratos?")],
    fragments=[],
)


class TestDocumentQuestionAuth:
    def test_missing_auth_returns_401(self, client):
        response = client.post(URL, json=VALID_BODY)
        assert response.status_code == 401

    def test_missing_permission_returns_403(self, client, make_auth_headers, mock_document_question_service):
        response = client.post(URL, json=VALID_BODY, headers=make_auth_headers(permissions=[]))
        assert response.status_code == 403

    def test_wrong_permission_returns_403(self, client, make_auth_headers, mock_document_question_service):
        response = client.post(URL, json=VALID_BODY, headers=make_auth_headers(permissions=["LLM_AGENT"]))
        assert response.status_code == 403


class TestDocumentQuestionValidation:
    def test_empty_messages_returns_422(self, client, auth_headers, mock_document_question_service):
        response = client.post(URL, json={"messages": []}, headers=auth_headers)
        assert response.status_code == 422

    def test_last_message_not_human_returns_422(self, client, auth_headers, mock_document_question_service):
        body = {"messages": [
            {"role": "human", "content": "Pregunta"},
            {"role": "assistant", "content": "Respuesta"},
        ]}
        response = client.post(URL, json=body, headers=auth_headers)
        assert response.status_code == 422

    def test_blank_message_content_returns_422(self, client, auth_headers, mock_document_question_service):
        body = {"messages": [{"role": "human", "content": "  "}]}
        response = client.post(URL, json=body, headers=auth_headers)
        assert response.status_code == 422

    def test_missing_messages_field_returns_422(self, client, auth_headers, mock_document_question_service):
        response = client.post(URL, json={}, headers=auth_headers)
        assert response.status_code == 422

    def test_invalid_role_returns_422(self, client, auth_headers, mock_document_question_service):
        body = {"messages": [{"role": "user", "content": "Pregunta"}]}
        response = client.post(URL, json=body, headers=auth_headers)
        assert response.status_code == 422


class TestDocumentQuestionSuccess:
    def test_valid_request_returns_200(self, client, auth_headers, mock_document_question_service):
        mock_document_question_service.execute_document_question.return_value = _RESPONSE
        response = client.post(URL, json=VALID_BODY, headers=auth_headers)
        assert response.status_code == 200

    def test_response_has_question_and_answer(self, client, auth_headers, mock_document_question_service):
        mock_document_question_service.execute_document_question.return_value = _RESPONSE
        body = client.post(URL, json=VALID_BODY, headers=auth_headers).json()
        assert "question" in body
        assert "answer" in body

    def test_response_has_fragments_list(self, client, auth_headers, mock_document_question_service):
        mock_document_question_service.execute_document_question.return_value = _RESPONSE
        body = client.post(URL, json=VALID_BODY, headers=auth_headers).json()
        assert "fragments" in body
        assert isinstance(body["fragments"], list)

    def test_missing_chat_id_returns_422(self, client, auth_headers, mock_document_question_service):
        body = {k: v for k, v in VALID_BODY.items() if k != "chat_id"}
        response = client.post(URL, json=body, headers=auth_headers)
        assert response.status_code == 422

    def test_service_unavailable_returns_503(self, client, auth_headers, app):
        original = getattr(app.state, "document_question_service", None)
        try:
            if hasattr(app.state, "document_question_service"):
                delattr(app.state, "document_question_service")
            response = client.post(URL, json=VALID_BODY, headers=auth_headers)
            assert response.status_code == 503
        finally:
            if original is not None:
                app.state.document_question_service = original
