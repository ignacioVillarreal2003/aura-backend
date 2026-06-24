"""
Tests for the NeMo Guardrails input-filter middleware over real endpoints.

The guardrails service is mocked at app.state level: these tests cover the
middleware wiring (extraction, blocking, pass-through and fail modes), not the
NeMo rails themselves.
"""
from contextlib import suppress
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.infrastructure.guardrails.nemo_guardrails_service import GuardrailsVerdict

CHAT_URL = "/api/v1/general-chat"

VALID_CHAT_BODY = {
    "messages": [{"role": "human", "content": "hola, ¿qué dice el reglamento?"}],
    "chat_id": 1,
    "document_ids": [],
}


@pytest.fixture
def mock_guardrails(app):
    guard = SimpleNamespace(
        is_active=True,
        settings=SimpleNamespace(blocked_message="Bloqueado por seguridad."),
        check_input=AsyncMock(return_value=GuardrailsVerdict(allowed=True)),
    )
    app.state.nemo_guardrails = guard
    yield guard
    with suppress(AttributeError):
        delattr(app.state, "nemo_guardrails")


@pytest.fixture
def mock_general_chat_service(app):
    mock = AsyncMock()
    app.state.general_chat_service = mock
    yield mock
    with suppress(AttributeError):
        delattr(app.state, "general_chat_service")


class TestGuardrailsMiddleware:
    def test_blocked_input_returns_400(
            self, client, auth_headers, mock_guardrails, mock_general_chat_service
    ):
        mock_guardrails.check_input.return_value = GuardrailsVerdict(
            allowed=False, reason="self check input"
        )
        response = client.post(CHAT_URL, json=VALID_CHAT_BODY, headers=auth_headers)
        assert response.status_code == 400
        assert response.json()["error"] == "input_blocked_by_guardrails"
        mock_general_chat_service.execute_general_chat.assert_not_called()

    def test_allowed_input_reaches_the_service(
            self, client, auth_headers, mock_guardrails, mock_general_chat_service
    ):
        from app.domain.dtos.user_interactions.general_chat.general_chat_response import (
            GeneralChatResponse,
        )

        mock_general_chat_service.execute_general_chat.return_value = GeneralChatResponse(
            answer="respuesta",
            messages=[{"role": "assistant", "content": "respuesta"}],
            fragments=[],
        )
        response = client.post(CHAT_URL, json=VALID_CHAT_BODY, headers=auth_headers)
        assert response.status_code == 200
        mock_guardrails.check_input.assert_awaited_once_with("hola, ¿qué dice el reglamento?")
        request_arg = mock_general_chat_service.execute_general_chat.await_args.kwargs
        assert request_arg or mock_general_chat_service.execute_general_chat.await_args.args

    def test_inactive_guardrails_passes_through(
            self, client, auth_headers, mock_guardrails, mock_general_chat_service
    ):
        from app.domain.dtos.user_interactions.general_chat.general_chat_response import (
            GeneralChatResponse,
        )

        mock_guardrails.is_active = False
        mock_general_chat_service.execute_general_chat.return_value = GeneralChatResponse(
            answer="ok", messages=[{"role": "assistant", "content": "ok"}], fragments=[]
        )
        response = client.post(CHAT_URL, json=VALID_CHAT_BODY, headers=auth_headers)
        assert response.status_code == 200
        mock_guardrails.check_input.assert_not_called()

    def test_check_failure_returns_503(
            self, client, auth_headers, mock_guardrails, mock_general_chat_service
    ):
        mock_guardrails.check_input.side_effect = RuntimeError("guard caído")
        response = client.post(CHAT_URL, json=VALID_CHAT_BODY, headers=auth_headers)
        assert response.status_code == 503
        assert response.json()["error"] == "guardrails_unavailable"

    def test_health_is_not_filtered(self, client, mock_guardrails):
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        mock_guardrails.check_input.assert_not_called()

    def test_blocked_before_validation_errors(self, client, auth_headers, mock_guardrails):
        mock_guardrails.check_input.return_value = GuardrailsVerdict(allowed=False)
        body = {"messages": [{"role": "human", "content": "texto malicioso"}]}
        response = client.post(CHAT_URL, json=body, headers=auth_headers)
        assert response.status_code == 400
        assert response.json()["error"] == "input_blocked_by_guardrails"
