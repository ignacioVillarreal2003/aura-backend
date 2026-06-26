"""
Tests for exception handler response shapes (exception_handlers.py).

Uses a dedicated mini-app with test-only routes so we can raise exceptions
without touching production controllers.
"""
import pytest
from fastapi import FastAPI, HTTPException
from starlette.testclient import TestClient

from app.api.handlers.exception_handlers import register_exception_handlers
from app.application.exceptions.app_exception import AppException


def _build_handler_app() -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/raise-app-exception")
    async def _app_exc():
        raise AppException("something went wrong", status_code=400, code="CustomCode")

    @app.get("/raise-app-exception-500")
    async def _app_exc_500():
        raise AppException("internal failure", status_code=500)

    @app.get("/raise-http-exception")
    async def _http_exc():
        raise HTTPException(status_code=418, detail="I'm a teapot")

    @app.get("/raise-generic-exception")
    async def _generic_exc():
        raise RuntimeError("unexpected boom")

    return app


@pytest.fixture(scope="module")
def handler_client():
    with TestClient(_build_handler_app(), raise_server_exceptions=False) as c:
        yield c


class TestAppExceptionHandler:
    def test_status_code_is_forwarded(self, handler_client):
        response = handler_client.get("/raise-app-exception")
        assert response.status_code == 400

    def test_response_contains_error_and_message(self, handler_client):
        body = handler_client.get("/raise-app-exception").json()
        assert body["error"] == "CustomCode"
        assert body["message"] == "something went wrong"

    def test_500_app_exception_status(self, handler_client):
        response = handler_client.get("/raise-app-exception-500")
        assert response.status_code == 500

    def test_default_code_is_class_name(self, handler_client):
        body = handler_client.get("/raise-app-exception-500").json()
        assert body["error"] == "AppException"


class TestRequestValidationHandler:
    def test_missing_required_field_returns_422(self, handler_client):
        pass

    def test_validation_error_format(self, client, auth_headers, mock_document_classify_service):
        response = client.post(
            "/api/v1/document-classify",
            json={"document_ids": []},
            headers=auth_headers,
        )
        assert response.status_code == 422
        body = response.json()
        assert body["error"] == "ValidationError"
        assert body["message"] == "Request validation failed"
        assert "detail" in body


class TestHttpExceptionHandler:
    def test_status_code_is_forwarded(self, handler_client):
        response = handler_client.get("/raise-http-exception")
        assert response.status_code == 418

    def test_response_contains_error_and_message(self, handler_client):
        body = handler_client.get("/raise-http-exception").json()
        assert body["error"] == "HttpError"
        assert body["message"] == "I'm a teapot"


class TestGeneralExceptionHandler:
    def test_unexpected_exception_returns_500(self, handler_client):
        response = handler_client.get("/raise-generic-exception")
        assert response.status_code == 500

    def test_response_shape(self, handler_client):
        body = handler_client.get("/raise-generic-exception").json()
        assert body["error"] == "InternalServerError"
        assert "message" in body


class TestRoutingErrorsUseAppEnvelope:
    """Starlette raises the base HTTPException for unmatched routes/methods;
    the handler must be registered for it so 404/405 share the app envelope."""

    def test_unknown_path_uses_app_envelope(self, handler_client):
        response = handler_client.get("/does-not-exist")
        assert response.status_code == 404
        body = response.json()
        assert body["error"] == "HttpError"
        assert body["message"] == "Not Found"

    def test_method_not_allowed_uses_app_envelope(self, handler_client):
        response = handler_client.post("/raise-http-exception")
        assert response.status_code == 405
        body = response.json()
        assert body["error"] == "HttpError"
        assert body["message"] == "Method Not Allowed"
