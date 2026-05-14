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

TEST_USER_ID = 42
TEST_USER_EMAIL = "user@test.com"

ALL_PERMISSIONS = [
    "LLM_DOCUMENT_QUESTION",
    "LLM_DOCUMENT_QUESTION_STREAM",
    "LLM_DOCUMENT_SUMMARY",
    "LLM_DOCUMENT_ACTION",
    "LLM_AGENT",
    "LLM_DOCUMENT_CLASSIFY",
    "LLM_FRAGMENT_ENRICH",
    "LLM_GRAPH_EXTRACTION",
    "LLM_GRAPH_QUERY_TRANSLATION",
    "LLM_RAG_AGENT",
]


def create_test_app() -> FastAPI:
    @asynccontextmanager
    async def _noop_lifespan(app: FastAPI):
        yield

    test_app = FastAPI(lifespan=_noop_lifespan)
    add_authentication_middleware(test_app)
    configure_cors(test_app)
    test_app.include_router(router, prefix="/api/v1")
    register_exception_handlers(test_app)

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
        response = client.post(url, json=body, headers=service_headers(permissions=["PERM"]))
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
    """Service headers pre-loaded with all LLM permissions."""
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
def mock_document_question_service(app):
    yield from _mock_service(app, "document_question_service")


@pytest.fixture
def mock_document_classify_service(app):
    yield from _mock_service(app, "document_classify_service")


@pytest.fixture
def mock_document_summary_service(app):
    yield from _mock_service(app, "document_summary_service")


@pytest.fixture
def mock_document_action_service(app):
    yield from _mock_service(app, "document_action_service")


@pytest.fixture
def mock_fragment_enrich_service(app):
    yield from _mock_service(app, "fragment_enrich_service")


@pytest.fixture
def mock_graph_extraction_service(app):
    yield from _mock_service(app, "graph_extraction_service")


@pytest.fixture
def mock_graph_query_translation_service(app):
    yield from _mock_service(app, "graph_query_translation_service")


@pytest.fixture
def mock_agent_service(app):
    yield from _mock_service(app, "agent_service")


@pytest.fixture
def mock_rag_agent_service(app):
    yield from _mock_service(app, "rag_agent_service")
