"""
Tests for POST /api/v1/agent
"""
from app.domain.dtos.agent.agent_response import AgentResponse

URL = "/api/v1/agent"

VALID_BODY = {
    "messages": [{"role": "human", "content": "Busca documentos sobre el contrato con Gamma."}],
}

_RESPONSE = AgentResponse(
    messages=[
        {"role": "human", "content": "Busca documentos sobre el contrato con Gamma."},
        {"role": "ai", "content": "Encontré los siguientes documentos relevantes."},
    ]
)


class TestAgentAuth:
    def test_missing_auth_returns_401(self, client):
        response = client.post(URL, json=VALID_BODY)
        assert response.status_code == 401

    def test_missing_permission_returns_403(self, client, service_headers, mock_agent_service):
        response = client.post(URL, json=VALID_BODY, headers=service_headers(permissions=[]))
        assert response.status_code == 403

    def test_wrong_permission_returns_403(self, client, service_headers, mock_agent_service):
        response = client.post(URL, json=VALID_BODY, headers=service_headers(permissions=["LLM_DOCUMENT_QUESTION"]))
        assert response.status_code == 403


class TestAgentValidation:
    def test_empty_messages_returns_422(self, client, auth_headers, mock_agent_service):
        body = {"messages": []}
        response = client.post(URL, json=body, headers=auth_headers)
        assert response.status_code == 422

    def test_missing_messages_returns_422(self, client, auth_headers, mock_agent_service):
        response = client.post(URL, json={}, headers=auth_headers)
        assert response.status_code == 422

    def test_last_message_not_human_returns_422(self, client, auth_headers, mock_agent_service):
        body = {
            "messages": [
                {"role": "human", "content": "Hola"},
                {"role": "ai", "content": "Hola, ¿en qué te ayudo?"},
            ]
        }
        response = client.post(URL, json=body, headers=auth_headers)
        assert response.status_code == 422

    def test_invalid_role_returns_422(self, client, auth_headers, mock_agent_service):
        body = {"messages": [{"role": "unknown_role", "content": "Hola"}]}
        response = client.post(URL, json=body, headers=auth_headers)
        assert response.status_code == 422

    def test_empty_message_content_returns_422(self, client, auth_headers, mock_agent_service):
        body = {"messages": [{"role": "human", "content": ""}]}
        response = client.post(URL, json=body, headers=auth_headers)
        assert response.status_code == 422


class TestAgentSuccess:
    def test_valid_request_returns_200(self, client, auth_headers, mock_agent_service):
        mock_agent_service.execute_agent.return_value = _RESPONSE
        response = client.post(URL, json=VALID_BODY, headers=auth_headers)
        assert response.status_code == 200

    def test_response_has_messages(self, client, auth_headers, mock_agent_service):
        mock_agent_service.execute_agent.return_value = _RESPONSE
        body = client.post(URL, json=VALID_BODY, headers=auth_headers).json()
        assert "messages" in body
        assert isinstance(body["messages"], list)

    def test_service_unavailable_returns_503(self, client, auth_headers, app):
        original = getattr(app.state, "agent_service", None)
        try:
            if hasattr(app.state, "agent_service"):
                delattr(app.state, "agent_service")
            response = client.post(URL, json=VALID_BODY, headers=auth_headers)
            assert response.status_code == 503
        finally:
            if original is not None:
                app.state.agent_service = original
