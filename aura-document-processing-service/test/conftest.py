import os
os.environ.setdefault("AUTHENTICATION_PROVIDER_AUTHENTICATION_URL", "http://auth.test")

import base64
import json
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from app.api.controllers import router
from app.api.handlers.exception_handlers import register_exception_handlers
from app.application.authorization.authorizer import Authorizer
from app.configuration.cors_configuration import configure_cors
from app.configuration.middlewares.authentication_middleware import add_authentication_middleware
from app.infrastructure.http.authentication_provider.exceptions.authentication_provider_exception import (
    AuthenticationProviderInvalidTokenException,
)
from app.infrastructure.http.authentication_provider.interfaces.authentication_provider_interface import (
    AuthenticationProviderInterface,
)
from app.infrastructure.http.authentication_provider.dtos.authenticated_user_response import (
    AuthenticatedUserResponse,
)
from app.infrastructure.persistence.database.database_manager.database_manager import get_database_session

TEST_USER_ID = 42
TEST_USER_EMAIL = "user@test.com"

ALL_PERMISSIONS = [
    "DOCUMENT_CREATE",
    "DOCUMENT_UPDATE_MANAGE",
    "DOCUMENT_REEMBED_MANAGE",
    "DOCUMENT_REPROCESS_MANAGE",
    "DOCUMENT_ENRICH_MANAGE",
    "DOCUMENT_QUERY",
    "DOCUMENT_QUERY_MANAGE",
    "DOCUMENT_DELETE",
    "DOCUMENT_DELETE_MANAGE",
    "DOCUMENT_RESTORE_MANAGE",
    "DOCUMENT_DOWNLOAD",
    "DOCUMENT_DOWNLOAD_MANAGE",
    "DOCUMENT_SEARCH",
    "FRAGMENT_QUERY",
    "GRAPH_QUERY",
    "GRAPH_ENTITY",
    "GRAPH_PATH",
    "GRAPH_SEARCH",
    "GRAPH_ONTOLOGY",
    "GRAPH_STATS_MANAGE",
    "GRAPH_EXTRACT_MANAGE",
]


async def _mock_db_session():
    """Yield a MagicMock session so no real DB connection is needed."""
    yield MagicMock()


def make_bearer_token(user_id=TEST_USER_ID, email=TEST_USER_EMAIL, permissions=None) -> str:
    """Encode the user payload in the token so the fake provider can resolve it."""
    payload = {
        "id": user_id,
        "email": email,
        "permissions": permissions or [],
    }
    return base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()


class FakeAuthenticationProvider(AuthenticationProviderInterface):
    """Resolves the user from the token payload instead of calling the auth service."""

    async def validate_token(self, token: str) -> AuthenticatedUserResponse:
        try:
            payload = json.loads(base64.urlsafe_b64decode(token.encode()))
            return AuthenticatedUserResponse.model_validate(payload)
        except Exception as e:
            raise AuthenticationProviderInvalidTokenException("Invalid or expired token") from e


def create_test_app() -> FastAPI:
    @asynccontextmanager
    async def _noop_lifespan(app: FastAPI):
        yield

    test_app = FastAPI(lifespan=_noop_lifespan)
    add_authentication_middleware(test_app)
    configure_cors(test_app)
    test_app.include_router(router, prefix="/api/v1")
    register_exception_handlers(test_app)

    test_app.dependency_overrides[get_database_session] = _mock_db_session

    test_app.state.authentication_provider = FakeAuthenticationProvider()
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
    Factory for bearer auth headers.

    Usage:
        response = client.get(url, headers=service_headers(permissions=["PERM"]))
    """
    def _make(user_id=TEST_USER_ID, email=TEST_USER_EMAIL, permissions=None):
        token = make_bearer_token(user_id=user_id, email=email, permissions=permissions)
        return {"Authorization": f"Bearer {token}"}

    return _make


@pytest.fixture
def auth_headers(service_headers):
    """Bearer headers pre-loaded with all document-processing permissions."""
    return service_headers(permissions=ALL_PERMISSIONS)



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
def mock_update_document_service(app):
    yield from _mock_service(app, "update_document_service")


@pytest.fixture
def mock_restore_document_service(app):
    yield from _mock_service(app, "restore_document_service")


@pytest.fixture
def mock_document_download_service(app):
    yield from _mock_service(app, "document_download_service")


@pytest.fixture
def mock_fragment_query_service(app):
    yield from _mock_service(app, "fragment_query_service")


@pytest.fixture
def mock_graph_query_service(app):
    yield from _mock_service(app, "graph_query_service")


@pytest.fixture
def mock_graph_entity_service(app):
    yield from _mock_service(app, "graph_entity_service")


@pytest.fixture
def mock_graph_path_service(app):
    yield from _mock_service(app, "graph_path_service")


@pytest.fixture
def mock_bulk_dispatch_service(app):
    yield from _mock_service(app, "bulk_dispatch_service")
