"""Shared fixtures and helpers for API tests (no app package changes)."""

from __future__ import annotations

import io
import os
from contextlib import asynccontextmanager, contextmanager
from typing import Any, Iterator
from unittest.mock import AsyncMock, MagicMock

import pytest
from starlette.datastructures import Headers, UploadFile
from starlette.testclient import TestClient

from app.configuration.environment_variables import environment_variables
from app.infrastructure.http.authentication_provider.authentication_provider import (
    AuthenticationProvider,
)
from app.main import create_app


class _LifespanBypassASGI:
    """ASGI wrapper: completes lifespan without calling the inner app's lifespan (no DB/Rabbit startup)."""

    def __init__(self, app: Any) -> None:
        self._app = app

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") == "lifespan":
            while True:
                message = await receive()
                if message["type"] == "lifespan.startup":
                    await send({"type": "lifespan.startup.complete"})
                elif message["type"] == "lifespan.shutdown":
                    await send({"type": "lifespan.shutdown.complete"})
                    return
            return
        await self._app(scope, receive, send)


class FakeDBManager:
    """Minimal stand-in for DatabaseManager when ASGI lifespan is disabled."""

    is_initialized = True

    def __init__(self, session_mock: MagicMock | None = None) -> None:
        self._session_mock = session_mock or MagicMock()
        self._session_mock.commit = AsyncMock()
        self._session_mock.rollback = AsyncMock()
        self._session_mock.close = AsyncMock()

    @asynccontextmanager
    async def session(self) -> Any:
        yield self._session_mock


def service_auth_headers(
    *,
    api_key: str | None = None,
    user_id: int = 1,
    email: str = "test@example.com",
    roles: str | None = "user",
    permissions: str | None = "DOCUMENT_CREATE",
) -> dict[str, str]:
    """Service-to-service auth headers (matches AuthenticationProvider middleware)."""
    headers: dict[str, str] = {
        "X-Service-Api-Key": api_key if api_key is not None else environment_variables.service_api_key,
        "X-User-Id": str(user_id),
        "X-User-Email": email,
    }
    if roles is not None:
        headers["X-User-Roles"] = roles
    if permissions is not None:
        headers["X-User-Permissions"] = permissions
    return headers


def document_query_auth_headers(**kwargs: Any) -> dict[str, str]:
    """Headers for document-query routes (requires DOCUMENT_GET)."""
    return service_auth_headers(permissions="DOCUMENT_GET", **kwargs)


def make_upload_file(*, data: bytes, filename: str, content_type: str) -> UploadFile:
    """Build a Starlette UploadFile backed by BytesIO (seek/read/size work for validators)."""
    return UploadFile(
        file=io.BytesIO(data),
        filename=filename,
        headers=Headers({"content-type": content_type}),
    )


def attach_auth_and_db(app: Any) -> FakeDBManager:
    """Register auth provider and fake DB on app.state; returns the fake manager."""
    app.state.authentication_provider = AuthenticationProvider(MagicMock())
    db = FakeDBManager()
    app.state.db_manager = db
    return db


@contextmanager
def sync_http_client(app: Any) -> Iterator[TestClient]:
    """Sync TestClient against the app without running the real FastAPI lifespan."""
    wrapped = _LifespanBypassASGI(app)
    with TestClient(wrapped) as test_client:
        yield test_client


@pytest.fixture
def app() -> Any:
    return create_app()


@pytest.fixture
def client(app: Any) -> Iterator[TestClient]:
    with sync_http_client(app) as test_client:
        yield test_client


@pytest.fixture
def app_with_auth_db(app: Any) -> Any:
    attach_auth_and_db(app)
    return app


@pytest.fixture
def client_with_auth_db(app_with_auth_db: Any) -> Iterator[TestClient]:
    with sync_http_client(app_with_auth_db) as test_client:
        yield test_client


def pytest_collection_modifyitems(config: Any, items: list[Any]) -> None:
    run_integration = os.environ.get("RUN_INTEGRATION") == "1"
    run_slow = os.environ.get("RUN_SLOW") == "1"
    for item in items:
        if item.get_closest_marker("integration") and not run_integration:
            item.add_marker(
                pytest.mark.skip(
                    reason="Integration tests require RUN_INTEGRATION=1 and Docker (see tests/integration/)."
                )
            )
        elif (
            item.get_closest_marker("slow")
            and not item.get_closest_marker("integration")
            and not run_slow
        ):
            item.add_marker(
                pytest.mark.skip(
                    reason="Slow tests require RUN_SLOW=1 (e.g. HuggingFace splitter on CPU; may download weights)."
                )
            )
