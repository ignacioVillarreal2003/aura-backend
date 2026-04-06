"""GET document-query with mocked DocumentQueryService."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from app.domain.constants.document.document_mime_type import DocumentMimeType
from app.domain.constants.document.document_status import DocumentStatus
from app.domain.dtos.document.document_query_controller.document_list_response import DocumentListResponse
from app.domain.dtos.document.document_query_controller.document_response import DocumentResponse
from app.main import create_app
from tests.conftest import attach_auth_and_db, document_query_auth_headers, sync_http_client


def _sample_document_response() -> DocumentResponse:
    now = datetime.now(timezone.utc)
    return DocumentResponse(
        id=5,
        chat_id=1,
        name="q.pdf",
        description=None,
        mime_type=DocumentMimeType.pdf,
        status=DocumentStatus.uploaded,
        storage_url="s",
        file_size_bytes=100,
        type=None,
        category=None,
        text_cleaner_type=None,
        text_splitter_type=None,
        embedder_type=None,
        split_size=None,
        split_overlap=None,
        processing_started_at=now,
        processing_finished_at=None,
        created_by=1,
        created_at=now,
        updated_by=None,
        updated_at=None,
        deleted_by=None,
        deleted_at=None,
    )


def test_get_document_by_id_returns_200() -> None:
    app = create_app()
    attach_auth_and_db(app)
    svc = MagicMock()
    svc.get_document = AsyncMock(return_value=_sample_document_response())
    app.state.document_query_service = svc

    with sync_http_client(app) as client:
        response = client.get(
            "/api/document-query/document_controllers/5",
            headers=document_query_auth_headers(),
        )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == 5
    assert body["name"] == "q.pdf"
    svc.get_document.assert_awaited_once()


def test_list_documents_returns_200() -> None:
    app = create_app()
    attach_auth_and_db(app)
    svc = MagicMock()
    svc.get_documents = AsyncMock(
        return_value=DocumentListResponse(documents=[_sample_document_response()])
    )
    app.state.document_query_service = svc

    with sync_http_client(app) as client:
        response = client.get(
            "/api/document-query/documents",
            headers=document_query_auth_headers(),
        )

    assert response.status_code == 200
    data = response.json()
    assert len(data["documents"]) == 1
    assert data["documents"][0]["id"] == 5
