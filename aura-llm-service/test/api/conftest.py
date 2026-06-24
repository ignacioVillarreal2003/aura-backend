from contextlib import asynccontextmanager, suppress
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from app.api.controllers import router
from app.api.handlers.exception_handlers import register_exception_handlers
from app.application.authorization.authorizer import Authorizer
from app.application.authorization.permissions import Permissions
from app.configuration.cors_configuration import configure_cors
from app.configuration.middlewares.authentication_middleware import add_authentication_middleware
from app.configuration.middlewares.guardrails_middleware import add_guardrails_middleware
from app.infrastructure.http.authentication_provider.authentication_provider import AuthenticationProvider
from app.infrastructure.http.authentication_provider.dtos.authenticated_user_response import (
    AuthenticatedUserResponse,
)

TEST_USER_ID = 42
TEST_USER_EMAIL = "user@test.com"
TEST_BEARER_TOKEN = "Bearer test-jwt-token"

ALL_PERMISSIONS = [
    value
    for name, value in vars(Permissions).items()
    if not name.startswith("_")
]


def create_test_app() -> FastAPI:
    @asynccontextmanager
    async def _noop_lifespan(app: FastAPI):
        yield

    test_app = FastAPI(lifespan=_noop_lifespan)
    add_guardrails_middleware(test_app)
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
def mock_authentication_provider(app):
    """Replace the app's authentication provider with an AsyncMock for one test."""
    original = app.state.authentication_provider
    provider = AsyncMock()
    app.state.authentication_provider = provider
    yield provider
    app.state.authentication_provider = original


@pytest.fixture
def make_auth_headers(mock_authentication_provider):
    """
    Factory for JWT auth headers. The mocked provider resolves the bearer token
    to a user with the requested permissions.

    Usage:
        response = client.post(url, json=body, headers=make_auth_headers(permissions=["PERM"]))
    """

    def _make(user_id=TEST_USER_ID, email=TEST_USER_EMAIL, permissions=None):
        mock_authentication_provider.validate_token.return_value = AuthenticatedUserResponse(
            id=user_id,
            email=email,
            username="tester",
            roles=[],
            permissions=permissions or [],
        )
        return {"Authorization": TEST_BEARER_TOKEN}

    return _make


@pytest.fixture
def auth_headers(make_auth_headers):
    """JWT headers resolved to a user holding every LLM permission."""
    return make_auth_headers(permissions=ALL_PERMISSIONS)



def _mock_service(app, attr: str):
    mock = AsyncMock()
    setattr(app.state, attr, mock)
    yield mock
    with suppress(AttributeError):
        delattr(app.state, attr)


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
def mock_fragment_contextualize_service(app):
    yield from _mock_service(app, "fragment_contextualize_service")


@pytest.fixture
def mock_graph_extraction_service(app):
    yield from _mock_service(app, "graph_extraction_service")


@pytest.fixture
def mock_graph_query_translation_service(app):
    yield from _mock_service(app, "graph_query_translation_service")


@pytest.fixture
def mock_rag_agent_service(app):
    yield from _mock_service(app, "rag_agent_service")
