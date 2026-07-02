from app.domain.dtos.processing.feedback_evaluation.feedback_evaluation_response import (
    FeedbackEvaluationResponse,
)

URL = "/api/v1/feedback-evaluate"

VALID_BODY = {
    "user_query": "¿Cuál es el procedimiento de evacuación?",
    "assistant_response": "No tengo información sobre eso.",
    "chat_history": [{"role": "human", "content": "¿Cuál es el procedimiento de evacuación?"}],
    "fragments": [],
    "feedback_reason": "incomplete",
    "feedback_comment": "Faltó detalle operativo.",
    "mode": "rag",
}

_RESPONSE = FeedbackEvaluationResponse(
    failure_category="retrieval_miss",
    failure_explanation="El contexto recuperado no contenía el procedimiento solicitado.",
    expected_output="El procedimiento de evacuación consiste en...",
    confidence_score=0.82,
    judge_model="judge-model",
)


class TestFeedbackEvaluationAuth:
    def test_missing_auth_returns_401(self, client):
        response = client.post(URL, json=VALID_BODY)
        assert response.status_code == 401

    def test_missing_permission_returns_403(self, client, make_auth_headers, mock_feedback_evaluation_service):
        response = client.post(URL, json=VALID_BODY, headers=make_auth_headers(permissions=[]))
        assert response.status_code == 403

    def test_wrong_permission_returns_403(self, client, make_auth_headers, mock_feedback_evaluation_service):
        response = client.post(URL, json=VALID_BODY, headers=make_auth_headers(permissions=["LLM_AGENT"]))
        assert response.status_code == 403


class TestFeedbackEvaluationValidation:
    def test_missing_user_query_returns_422(self, client, auth_headers, mock_feedback_evaluation_service):
        body = {k: v for k, v in VALID_BODY.items() if k != "user_query"}
        response = client.post(URL, json=body, headers=auth_headers)
        assert response.status_code == 422

    def test_missing_assistant_response_returns_422(self, client, auth_headers, mock_feedback_evaluation_service):
        body = {k: v for k, v in VALID_BODY.items() if k != "assistant_response"}
        response = client.post(URL, json=body, headers=auth_headers)
        assert response.status_code == 422


class TestFeedbackEvaluationSuccess:
    def test_valid_request_returns_200(self, client, auth_headers, mock_feedback_evaluation_service):
        mock_feedback_evaluation_service.execute_feedback_evaluation.return_value = _RESPONSE
        response = client.post(URL, json=VALID_BODY, headers=auth_headers)
        assert response.status_code == 200

    def test_response_has_judge_fields(self, client, auth_headers, mock_feedback_evaluation_service):
        mock_feedback_evaluation_service.execute_feedback_evaluation.return_value = _RESPONSE
        body = client.post(URL, json=VALID_BODY, headers=auth_headers).json()
        assert body["failure_category"] == "retrieval_miss"
        assert body["judge_model"] == "judge-model"
        assert body["confidence_score"] == 0.82

    def test_minimal_body_returns_200(self, client, auth_headers, mock_feedback_evaluation_service):
        mock_feedback_evaluation_service.execute_feedback_evaluation.return_value = _RESPONSE
        body = {
            "user_query": "pregunta",
            "assistant_response": "respuesta",
        }
        response = client.post(URL, json=body, headers=auth_headers)
        assert response.status_code == 200

    def test_service_unavailable_returns_503(self, client, auth_headers, app):
        original = getattr(app.state, "feedback_evaluation_service", None)
        try:
            if hasattr(app.state, "feedback_evaluation_service"):
                delattr(app.state, "feedback_evaluation_service")
            response = client.post(URL, json=VALID_BODY, headers=auth_headers)
            assert response.status_code == 503
        finally:
            if original is not None:
                app.state.feedback_evaluation_service = original
