"""
Tests for:
  GET /api/v1/health  (liveness — always 200, no auth)
  GET /api/v1/ready   (readiness — 200/503 depending on app.state)
"""
from unittest.mock import MagicMock

HEALTH_URL = "/api/v1/health"
READY_URL = "/api/v1/ready"


class TestLivenessEndpoint:
    def test_returns_200(self, client):
        response = client.get(HEALTH_URL)
        assert response.status_code == 200

    def test_returns_ok_status(self, client):
        response = client.get(HEALTH_URL)
        assert response.json()["status"] == "ok"

    def test_no_auth_required(self, client):
        response = client.get(HEALTH_URL)
        assert response.status_code == 200


class TestReadinessEndpoint:
    def test_no_auth_required(self, client):
        response = client.get(READY_URL)
        assert response.status_code in (200, 503)

    def test_degraded_when_http_client_missing(self, app, client):
        original = getattr(app.state, "http_client", None)
        try:
            if hasattr(app.state, "http_client"):
                delattr(app.state, "http_client")
            response = client.get(READY_URL)
            assert response.status_code == 503
            assert response.json()["status"] == "degraded"
            assert response.json()["checks"]["http_client"]["status"] == "not_configured"
        finally:
            if original is not None:
                app.state.http_client = original

    def test_degraded_when_http_client_errors(self, app, client):
        mock_http = MagicMock()
        mock_http.health_check.side_effect = Exception("connection refused")
        original = getattr(app.state, "http_client", None)
        app.state.http_client = mock_http
        try:
            response = client.get(READY_URL)
            assert response.status_code == 503
            assert response.json()["checks"]["http_client"]["status"] == "error"
        finally:
            if original is not None:
                app.state.http_client = original
            elif hasattr(app.state, "http_client"):
                delattr(app.state, "http_client")

    def test_degraded_when_ollama_unhealthy(self, app, client):
        mock_ollama = MagicMock()
        mock_ollama.is_healthy.return_value = False
        original = getattr(app.state, "ollama_llm_facade", None)
        app.state.ollama_llm_facade = mock_ollama
        try:
            response = client.get(READY_URL)
            assert response.status_code == 503
            assert response.json()["checks"]["ollama"]["status"] == "error"
        finally:
            if original is not None:
                app.state.ollama_llm_facade = original
            elif hasattr(app.state, "ollama_llm_facade"):
                delattr(app.state, "ollama_llm_facade")

    def test_all_ok_returns_200(self, app, client):
        mock_http = MagicMock()
        mock_http.health_check.return_value = {"status": "healthy"}
        mock_ollama = MagicMock()
        mock_ollama.is_healthy.return_value = True
        mock_ollama.tools_bound = True

        original_http = getattr(app.state, "http_client", None)
        original_ollama = getattr(app.state, "ollama_llm_facade", None)
        app.state.http_client = mock_http
        app.state.ollama_llm_facade = mock_ollama
        try:
            response = client.get(READY_URL)
            assert response.status_code == 200
            assert response.json()["status"] == "ok"
        finally:
            if original_http is not None:
                app.state.http_client = original_http
            elif hasattr(app.state, "http_client"):
                delattr(app.state, "http_client")
            if original_ollama is not None:
                app.state.ollama_llm_facade = original_ollama
            elif hasattr(app.state, "ollama_llm_facade"):
                delattr(app.state, "ollama_llm_facade")

    def test_response_includes_checks_field(self, client):
        response = client.get(READY_URL)
        assert "checks" in response.json()
