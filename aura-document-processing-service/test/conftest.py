import os
# Set before any app module is imported so EnvironmentVariables() picks up these values.
os.environ.setdefault("SERVICE_API_KEY", "test-service-key")
os.environ.setdefault("AUTHENTICATION_PROVIDER_AUTHENTICATION_URL", "http://auth.test")

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from app.api.controllers import router
from app.api.handlers.exception_handlers import register_exception_handlers
from app.application.authorization.authorizer import Authorizer
from app.configuration.cors_configuration import configure_cors
from app.configuration.environment_variables import environment_variables
from app.configuration.middlewares.authentication_middleware import add_authentication_middleware
from app.infrastructure.http.authentication_provider.authentication_provider import AuthenticationProvider
from app.infrastructure.persistence.database.database_manager.database_manager import get_database_session

TEST_USER_ID = 42
TEST_USER_EMAIL = "user@test.com"

ALL_PERMISSIONS = [
    "INGEST_DOCUMENT",
    "GET_DOCUMENT",
    "LIST_DOCUMENTS",
    "LIST_DOCUMENTS_BY_CHAT",
    "DOWNLOAD_DOCUMENT",
    "SOFT_DELETE_DOCUMENT",
    "SOFT_DELETE_DOCUMENTS_BY_CHAT",
    "POST_PROCESS_DOCUMENTS_START_ALL",
    "POST_PROCESS_DOCUMENTS_START",
    "POST_PROCESS_DOCUMENTS_STATUS",
    "POST_PROCESS_DOCUMENTS_STOP",
    "POST_PROCESS_FRAGMENTS_START_ALL",
    "POST_PROCESS_FRAGMENTS_START",
    "POST_PROCESS_FRAGMENTS_STATUS",
    "POST_PROCESS_FRAGMENTS_STOP",
    "LIST_CONTEXT_FRAGMENTS_BY_QUESTION",
    "LIST_CONTEXT_FRAGMENTS_BY_DOCUMENTS",
    "GRAPH_QUERY",
    "GRAPH_ENTITY",
    "GRAPH_PATH",
]


async def _mock_db_session():
    """Yield a MagicMock session so no real DB connection is needed."""
    yield MagicMock()


def create_test_app() -> FastAPI:
    @asynccontextmanager
    async def _noop_lifespan(app: FastAPI):
        yield

    test_app = FastAPI(lifespan=_noop_lifespan)
    add_authentication_middleware(test_app)
    configure_cors(test_app)
    test_app.include_router(router, prefix="/api/v1")
    register_exception_handlers(test_app)

    # Replace the real DB session dependency with a no-op mock.
    test_app.dependency_overrides[get_database_session] = _mock_db_session

    mock_http = MagicMock()
    test_app.state.authentication_provider = AuthenticationProvider(http_client=mock_http)
    test_app.state.authorizer = Authorizer()

    return test_app


@pytest.fixture(scope="session")
def app():
    return create_test_app()


@pytest.fixture(scope="session")
def client(app):
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture
def service_headers():
    """
    Factory for service-to-service auth headers.

    Usage:
        response = client.get(url, headers=service_headers(permissions=["PERM"]))
    """
    def _make(user_id=TEST_USER_ID, email=TEST_USER_EMAIL, permissions=None):
        headers = {
            "X-Service-Api-Key": environment_variables.service_api_key,
            "X-User-Id": str(user_id),
            "X-User-Email": email,
        }
        if permissions is not None:
            headers["X-User-Permissions"] = ",".join(permissions)
        return headers

    return _make


@pytest.fixture
def auth_headers(service_headers):
    """Service headers pre-loaded with all document-processing permissions."""
    return service_headers(permissions=ALL_PERMISSIONS)


# ── Per-service mock helpers ──────────────────────────────────────────────────

def _mock_service(app, attr: str):
    mock = AsyncMock()
    setattr(app.state, attr, mock)
    yield mock
    try:
        delattr(app.state, attr)
    except AttributeError:
        pass


@pytest.fixture
def mock_create_document_service(app):
    yield from _mock_service(app, "create_document_service")


@pytest.fixture
def mock_delete_document_service(app):
    yield from _mock_service(app, "delete_document_service")


@pytest.fixture
def mock_document_query_service(app):
    yield from _mock_service(app, "document_query_service")


@pytest.fixture
def mock_document_download_service(app):
    yield from _mock_service(app, "document_download_service")


@pytest.fixture
def mock_post_process_document_service(app):
    yield from _mock_service(app, "post_process_document_service")


@pytest.fixture
def mock_fragment_query_service(app):
    yield from _mock_service(app, "fragment_query_service")


@pytest.fixture
def mock_post_process_fragment_service(app):
    yield from _mock_service(app, "post_process_fragment_service")


@pytest.fixture
def mock_graph_query_service(app):
    yield from _mock_service(app, "graph_query_service")


@pytest.fixture
def mock_graph_entity_service(app):
    yield from _mock_service(app, "graph_entity_service")


@pytest.fixture
def mock_graph_path_service(app):
    yield from _mock_service(app, "graph_path_service")
