"""Tests for the cross-cutting API hardening pieces: request body size limit,
SSE heartbeats and X-Request-ID propagation."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI, Request
from pydantic import BaseModel
from starlette.testclient import TestClient

import app.api.sse as sse_module
from app.api.sse import sse_response
from app.configuration.middlewares.body_size_limit_middleware import BodySizeLimitMiddleware
from app.configuration.middlewares.logging_middleware import add_logging_middleware
from app.infrastructure.http.http_client.http_client import HttpClient
from app.infrastructure.http.request_id_context import get_request_id, set_request_id



def _body_limit_app(max_body_bytes: int) -> FastAPI:
    app = FastAPI()
    app.add_middleware(BodySizeLimitMiddleware, max_body_bytes=max_body_bytes)

    @app.post("/echo")
    async def echo(request: Request):
        body = await request.body()
        return {"received": len(body)}

    return app


def test_body_under_limit_is_accepted():
    client = TestClient(_body_limit_app(max_body_bytes=100))
    response = client.post("/echo", content=b"x" * 50)
    assert response.status_code == 200
    assert response.json() == {"received": 50}


def test_declared_content_length_over_limit_is_rejected():
    client = TestClient(_body_limit_app(max_body_bytes=100))
    response = client.post("/echo", content=b"x" * 101)
    assert response.status_code == 413
    assert response.json()["error"] == "RequestBodyTooLarge"


def test_chunked_body_over_limit_is_rejected():
    client = TestClient(_body_limit_app(max_body_bytes=100))
    response = client.post("/echo", content=iter([b"x" * 60, b"x" * 60]))
    assert response.status_code == 413
    assert response.json()["error"] == "RequestBodyTooLarge"



class _Event(BaseModel):
    type: str = "delta"
    value: str = "hola"


def test_sse_emits_heartbeat_while_waiting_for_slow_events(monkeypatch):
    monkeypatch.setattr(sse_module, "_HEARTBEAT_INTERVAL_SECONDS", 0.01)

    async def slow_events():
        await asyncio.sleep(0.08)
        yield _Event()

    app = FastAPI()

    @app.post("/stream")
    async def stream():
        return sse_response(slow_events())

    client = TestClient(app)
    response = client.post("/stream")
    assert response.status_code == 200
    assert b": ping\n\n" in response.content
    assert b'"value":"hola"' in response.content


def test_sse_emits_events_without_heartbeat_when_fast():
    async def fast_events():
        yield _Event(value="uno")
        yield _Event(value="dos")

    app = FastAPI()

    @app.post("/stream")
    async def stream():
        return sse_response(fast_events())

    client = TestClient(app)
    response = client.post("/stream")
    assert response.status_code == 200
    assert b": ping" not in response.content
    assert response.content.count(b"data: ") == 2



def test_logging_middleware_sets_request_id_contextvar():
    app = FastAPI()
    add_logging_middleware(app)

    @app.get("/whoami")
    async def whoami():
        return {"request_id": get_request_id()}

    client = TestClient(app)
    response = client.get("/whoami", headers={"X-Request-ID": "rid-123"})
    assert response.json() == {"request_id": "rid-123"}
    assert response.headers["X-Request-ID"] == "rid-123"


@pytest.mark.asyncio
async def test_http_client_forwards_request_id_header():
    http_client = HttpClient()
    await http_client.start()
    try:
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.status_code = 200
        http_client._client = MagicMock()
        http_client._client.request = AsyncMock(return_value=mock_response)

        set_request_id("rid-456")
        try:
            await http_client.post("http://downstream.test/x", json={})
        finally:
            set_request_id(None)

        _, kwargs = http_client._client.request.call_args
        assert kwargs["headers"]["X-Request-ID"] == "rid-456"
    finally:
        await http_client.stop()


@pytest.mark.asyncio
async def test_http_client_does_not_override_explicit_request_id():
    http_client = HttpClient()
    await http_client.start()
    try:
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.status_code = 200
        http_client._client = MagicMock()
        http_client._client.request = AsyncMock(return_value=mock_response)

        set_request_id("rid-789")
        try:
            await http_client.post(
                "http://downstream.test/x",
                json={},
                headers={"X-Request-ID": "explicit"},
            )
        finally:
            set_request_id(None)

        _, kwargs = http_client._client.request.call_args
        assert kwargs["headers"]["X-Request-ID"] == "explicit"
    finally:
        await http_client.stop()
