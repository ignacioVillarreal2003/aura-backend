"""
Tests for POST /api/v1/rag-agent
"""
from app.domain.dtos.user_interactions.agent.agent_response import AgentResponse

URL = "/api/v1/rag-agent"

VALID_BODY = {
    "messages": [{"role": "human", "content": "¿Qué dice el contrato sobre las penalidades?"}],
    "chat_id": 1,
}

_RESPONSE = AgentResponse(
    messages=[
        {"role": "human", "content": "¿Qué dice el contrato sobre las penalidades?"},
        {"role": "assistant", "content": "Según el contrato, las penalidades son las siguientes."},
    ]
)


class TestRagAgentAuth:
    def test_missing_auth_returns_401(self, client):
        response = client.post(URL, json=VALID_BODY)
        assert response.status_code == 401

    def test_missing_permission_returns_403(self, client, make_auth_headers, mock_rag_agent_service):
        response = client.post(URL, json=VALID_BODY, headers=make_auth_headers(permissions=[]))
        assert response.status_code == 403

    def test_wrong_permission_returns_403(self, client, make_auth_headers, mock_rag_agent_service):
        response = client.post(URL, json=VALID_BODY, headers=make_auth_headers(permissions=["LLM_DOCUMENT_QUESTION"]))
        assert response.status_code == 403


class TestRagAgentValidation:
    def test_empty_messages_returns_422(self, client, auth_headers, mock_rag_agent_service):
        body = {"messages": []}
        response = client.post(URL, json=body, headers=auth_headers)
        assert response.status_code == 422

    def test_missing_messages_returns_422(self, client, auth_headers, mock_rag_agent_service):
        response = client.post(URL, json={}, headers=auth_headers)
        assert response.status_code == 422

    def test_last_message_not_human_returns_422(self, client, auth_headers, mock_rag_agent_service):
        body = {
            "messages": [
                {"role": "human", "content": "Hola"},
                {"role": "assistant", "content": "¿En qué te ayudo?"},
            ]
        }
        response = client.post(URL, json=body, headers=auth_headers)
        assert response.status_code == 422

    def test_invalid_role_returns_422(self, client, auth_headers, mock_rag_agent_service):
        body = {"messages": [{"role": "bot", "content": "Hola"}]}
        response = client.post(URL, json=body, headers=auth_headers)
        assert response.status_code == 422

    def test_empty_message_content_returns_422(self, client, auth_headers, mock_rag_agent_service):
        body = {"messages": [{"role": "human", "content": ""}]}
        response = client.post(URL, json=body, headers=auth_headers)
        assert response.status_code == 422


class TestRagAgentSuccess:
    def test_valid_request_returns_200(self, client, auth_headers, mock_rag_agent_service):
        mock_rag_agent_service.execute.return_value = _RESPONSE
        response = client.post(URL, json=VALID_BODY, headers=auth_headers)
        assert response.status_code == 200

    def test_response_has_messages(self, client, auth_headers, mock_rag_agent_service):
        mock_rag_agent_service.execute.return_value = _RESPONSE
        body = client.post(URL, json=VALID_BODY, headers=auth_headers).json()
        assert "messages" in body
        assert isinstance(body["messages"], list)

    def test_service_unavailable_returns_503(self, client, auth_headers, app):
        original = getattr(app.state, "rag_agent_service", None)
        try:
            if hasattr(app.state, "rag_agent_service"):
                delattr(app.state, "rag_agent_service")
            response = client.post(URL, json=VALID_BODY, headers=auth_headers)
            assert response.status_code == 503
        finally:
            if original is not None:
                app.state.rag_agent_service = original
