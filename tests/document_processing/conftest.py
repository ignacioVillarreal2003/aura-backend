"""
Fixtures compartidas para los tests del aura-document-processing-service.

Estrategia:
- Se parchean startup_dependencies y shutdown_dependencies para evitar
  conexiones reales a PostgreSQL, MinIO y RabbitMQ.
- Los servicios (CreateDocumentService, DocumentQueryService, etc.) se
  reemplazan por AsyncMock en app.state.
- Se sobreescriben get_authenticated_user y get_database_session de FastAPI.
- El middleware de autenticación usa un provider mock que aprueba todas las
  peticiones automáticamente.
- Las dependencias ML pesadas (sentence_transformers, langchain, etc.) se
  mockean a nivel de sys.modules para evitar instalaciones pesadas en tests.
"""

import os
import sys

sys.path.insert(
    0,
    os.path.normpath(
        os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "..", "aura-document-processing-service",
        )
    ),
)

# ──────────────────────────────────────────────────────────────────────────────
# Mock de dependencias ML pesadas — DEBE ir ANTES de cualquier import del app
# ──────────────────────────────────────────────────────────────────────────────
from unittest.mock import MagicMock

_HEAVY_MODULES = [
    "sentence_transformers",
    "sentence_transformers.cross_encoder",
    "langchain",
    "langchain.text_splitter",
    "langchain_community",
    "langchain_core",
    "langchain_experimental",
    "langchain_huggingface",
    "langchain_ollama",
    "langchain_text_splitters",
    "torch",
    "transformers",
    "sklearn",
    "nltk",
    "docling",
    "PIL",
    "pytesseract",
    "pdf2image",
]
for _mod in _HEAVY_MODULES:
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

# ──────────────────────────────────────────────────────────────────────────────

from datetime import datetime, timezone
from io import BytesIO
from typing import AsyncIterator
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.constants.document.document_mime_type import DocumentMimeType
from app.domain.constants.document.document_status import DocumentStatus
from app.domain.dtos.document.create_document.create_document_response import CreateDocumentResponse
from app.domain.dtos.document.document_query.document_response import DocumentResponse
from app.domain.dtos.document.document_query.document_list_response import DocumentListResponse
from app.infrastructure.http.authentication_provider.authentication_provider import get_authenticated_user
from app.infrastructure.persistence.database.database_manager.database_manager import get_database_session

NOW = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

TEST_USER = AuthenticatedUser(
    id=1,
    email="test@aura.com",
    roles=["admin"],
    permissions=["DOCUMENT_CREATE", "DOCUMENT_READ", "DOCUMENT_DELETE"],
)


# ---------------------------------------------------------------------------
# Helpers para construir respuestas de prueba
# ---------------------------------------------------------------------------

def make_create_document_response(doc_id: int = 1, name: str = "doc.pdf") -> CreateDocumentResponse:
    return CreateDocumentResponse(
        id=doc_id,
        name=name,
        mime_type=DocumentMimeType.pdf,
        status=DocumentStatus.uploaded,
        storage_url=f"documents/{name}",
        file_size_bytes=1024,
        processing_started_at=NOW,
        created_by=TEST_USER.id,
        created_at=NOW,
    )


def make_document_response(doc_id: int = 1, name: str = "doc.pdf") -> DocumentResponse:
    return DocumentResponse(
        id=doc_id,
        name=name,
        mime_type=DocumentMimeType.pdf,
        status=DocumentStatus.processed,
        storage_url=f"documents/{name}",
        file_size_bytes=1024,
        processing_started_at=NOW,
        created_by=TEST_USER.id,
        created_at=NOW,
    )


def make_document_list_response(docs=None) -> DocumentListResponse:
    if docs is None:
        docs = [make_document_response()]
    return DocumentListResponse(documents=docs)


def make_pdf_upload(filename: str = "test.pdf", content: bytes = b"PDF content"):
    return ("raw_document", (filename, BytesIO(content), "application/pdf"))


def make_invalid_upload(filename: str = "malware.exe", content: bytes = b"MZ..."):
    return ("raw_document", (filename, BytesIO(content), "application/octet-stream"))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_create_service():
    return AsyncMock()


@pytest.fixture
def mock_query_service():
    return AsyncMock()


@pytest.fixture
def mock_delete_service():
    return AsyncMock()


@pytest.fixture
def client(mock_create_service, mock_query_service, mock_delete_service):
    async def fake_startup(app):
        mock_auth = MagicMock()
        mock_auth.evaluate_service_auth.return_value = TEST_USER
        app.state.authentication_provider = mock_auth
        app.state.create_document_service = mock_create_service
        app.state.document_query_service = mock_query_service
        app.state.delete_document_service = mock_delete_service
        app.state.db_manager = AsyncMock()

    async def fake_shutdown(app):
        pass

    async def mock_get_db() -> AsyncIterator[AsyncSession]:
        yield AsyncMock(spec=AsyncSession)

    from app.main import app as fastapi_app

    fastapi_app.dependency_overrides[get_authenticated_user] = lambda: TEST_USER
    fastapi_app.dependency_overrides[get_database_session] = mock_get_db

    with (
        patch("app.main.startup_dependencies", fake_startup),
        patch("app.main.shutdown_dependencies", fake_shutdown),
    ):
        with TestClient(fastapi_app, raise_server_exceptions=False) as c:
            yield c

    fastapi_app.dependency_overrides.clear()
