"""HTTP tests for POST /api/create-document."""

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from starlette.testclient import TestClient

from app.application.services.document.create_document_service.create_document_service import (
    CreateDocumentService,
)
from app.application.services.document.create_document_service.create_document_service_settings import (
    CreateDocumentServiceSettings,
)
from app.domain.constants.document.document_mime_type import DocumentMimeType
from app.domain.constants.document.document_status import DocumentStatus
from app.domain.dtos.document.create_document.create_document_response import CreateDocumentResponse
from app.main import create_app
from tests.constants import CT_DOCX, CT_PDF, DOCX_ZIP_PREFIX, PDF_MINIMAL
from tests.conftest import attach_auth_and_db, service_auth_headers, sync_http_client
from tests.test_create_document_service import _persisted_document, _rabbit_mock


@pytest.fixture
def create_document_client() -> tuple[TestClient, Any, MagicMock]:
    app = create_app()
    attach_auth_and_db(app)
    repo = AsyncMock()
    repo.create_document = AsyncMock(return_value=_persisted_document())
    storage = AsyncMock()
    storage.upload_document = AsyncMock(return_value="obj-http")
    rabbit = _rabbit_mock()
    app.state.create_document_service = CreateDocumentService(
        document_repository=repo,
        document_storage=storage,
        rabbitmq_manager=rabbit,
        create_document_service_settings=CreateDocumentServiceSettings(),
    )
    with sync_http_client(app) as client:
        yield client, app, rabbit


def test_create_pdf_success_returns_200(create_document_client: tuple[TestClient, Any, MagicMock]) -> None:
    client, _, _ = create_document_client
    response = client.post(
        "/api/create-document",
        headers=service_auth_headers(),
        data={"chat_id": "1", "prefer_docling": "false"},
        files={"raw_document": ("a.pdf", PDF_MINIMAL, CT_PDF)},
    )
    assert response.status_code == 200
    body = response.json()
    assert body.get("error") is None
    assert body["id"] == 42
    assert body["name"] == "a.pdf"
    assert body["mime_type"] == "pdf"


def test_create_docx_success(create_document_client: tuple[TestClient, Any, MagicMock]) -> None:
    client, app, _ = create_document_client
    repo = AsyncMock()
    repo.create_document = AsyncMock(
        return_value=_persisted_document(name="b.docx", mime=DocumentMimeType.docx)
    )
    storage = AsyncMock()
    storage.upload_document = AsyncMock(return_value="obj-docx")
    rabbit = _rabbit_mock()
    app.state.create_document_service = CreateDocumentService(
        document_repository=repo,
        document_storage=storage,
        rabbitmq_manager=rabbit,
        create_document_service_settings=CreateDocumentServiceSettings(),
    )

    response = client.post(
        "/api/create-document",
        headers=service_auth_headers(),
        data={"chat_id": "2", "prefer_docling": "false"},
        files={"raw_document": ("b.docx", DOCX_ZIP_PREFIX, CT_DOCX)},
    )
    assert response.status_code == 200
    assert response.json()["mime_type"] == "docx"


def test_prefer_docling_true_in_envelope(create_document_client: tuple[TestClient, Any, MagicMock]) -> None:
    from app.infrastructure.messaging.rabbitmq.dtos.commands.document_ingestion_command import (
        DocumentIngestionCommand,
    )
    from app.infrastructure.messaging.rabbitmq.dtos.envelope.message_envelope import MessageEnvelope

    client, _, rabbit = create_document_client
    response = client.post(
        "/api/create-document",
        headers=service_auth_headers(),
        data={"chat_id": "3", "prefer_docling": "true"},
        files={"raw_document": ("a.pdf", PDF_MINIMAL, CT_PDF)},
    )
    assert response.status_code == 200
    rabbit.publish.assert_awaited()
    body = rabbit.publish.await_args.kwargs["body"]
    env = MessageEnvelope.from_bytes(body, DocumentIngestionCommand)
    assert env.command.prefer_docling is True


def test_missing_permission_returns_403_json_shape(
    create_document_client: tuple[TestClient, Any, MagicMock],
) -> None:
    client, _, _ = create_document_client
    response = client.post(
        "/api/create-document",
        headers=service_auth_headers(permissions=""),
        data={"chat_id": "1", "prefer_docling": "false"},
        files={"raw_document": ("a.pdf", PDF_MINIMAL, CT_PDF)},
    )
    assert response.status_code == 403
    err = response.json()
    assert "error" in err and "message" in err


def test_missing_chat_id_returns_422(create_document_client: tuple[TestClient, Any, MagicMock]) -> None:
    client, _, _ = create_document_client
    response = client.post(
        "/api/create-document",
        headers=service_auth_headers(),
        data={"prefer_docling": "false"},
        files={"raw_document": ("a.pdf", PDF_MINIMAL, CT_PDF)},
    )
    assert response.status_code == 422
    detail = response.json().get("detail")
    assert detail is not None


def test_missing_raw_document_returns_422(create_document_client: tuple[TestClient, Any, MagicMock]) -> None:
    client, _, _ = create_document_client
    response = client.post(
        "/api/create-document",
        headers=service_auth_headers(),
        data={"chat_id": "1", "prefer_docling": "false"},
    )
    assert response.status_code == 422


def test_stub_service_delegates_to_controller() -> None:
    app = create_app()
    attach_auth_and_db(app)
    now = datetime.now(timezone.utc)
    stub_response = CreateDocumentResponse(
        id=99,
        name="stub.pdf",
        mime_type=DocumentMimeType.pdf,
        status=DocumentStatus.uploaded,
        storage_url="stub",
        file_size_bytes=10,
        processing_started_at=now,
        created_by=1,
        created_at=now,
    )
    svc = SimpleNamespace(create_document=AsyncMock(return_value=stub_response))
    app.state.create_document_service = svc  # type: ignore[assignment]

    with sync_http_client(app) as client:
        response = client.post(
            "/api/create-document",
            headers=service_auth_headers(),
            data={"chat_id": "1", "prefer_docling": "false"},
            files={"raw_document": ("stub.pdf", PDF_MINIMAL, CT_PDF)},
        )
    assert response.status_code == 200
    assert response.json()["id"] == 99
    svc.create_document.assert_awaited_once()
