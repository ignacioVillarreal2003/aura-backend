"""CreateDocumentService with mocked infrastructure."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.application.services.document.create_document_service.create_document_service import (
    CreateDocumentService,
)
from app.application.services.document.create_document_service.create_document_service_settings import (
    CreateDocumentServiceSettings,
)
from app.application.services.document.create_document_service.exceptions.create_document_service_exception import (
    CreateDocumentPersistenceException,
    CreateDocumentServiceException,
    CreateDocumentUnauthorizedException,
    CreateDocumentUploadException,
    CreateDocumentValidationException,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.constants.document.document_mime_type import DocumentMimeType
from app.domain.constants.document.document_status import DocumentStatus
from app.domain.dtos.document.create_document.create_document_request import CreateDocumentRequest
from app.infrastructure.messaging.rabbitmq.dtos.commands.document_ingestion_command import (
    DocumentIngestionCommand,
)
from app.infrastructure.messaging.rabbitmq.dtos.envelope.message_envelope import MessageEnvelope
from app.infrastructure.persistence.database.repositories.exceptions.database_exceptions import (
    DatabaseException,
)
from app.infrastructure.persistence.storages.document_storage.exceptions.document_storage_exception import (
    DocumentStorageException,
)
from tests.constants import CT_DOCX, CT_PDF, DOCX_ZIP_PREFIX, PDF_MINIMAL
from tests.conftest import make_upload_file


def _rabbit_mock() -> MagicMock:
    mq = MagicMock()
    mq.publish = AsyncMock()
    mq.settings = MagicMock()
    mq.settings.document_ingestion_queue = "document.ingestion"
    return mq


def _user(
    *,
    roles: list[str] | None = None,
    permissions: list[str] | None = None,
) -> AuthenticatedUser:
    return AuthenticatedUser(
        id=1,
        email="t@e.st",
        roles=roles if roles is not None else ["user"],
        permissions=permissions if permissions is not None else ["DOCUMENT_CREATE"],
    )


def _persisted_document(*, name: str = "a.pdf", mime: DocumentMimeType = DocumentMimeType.pdf) -> SimpleNamespace:
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=42,
        name=name,
        mime_type=mime,
        status=DocumentStatus.uploaded,
        storage_url="objects/abc",
        file_size_bytes=len(PDF_MINIMAL),
        processing_started_at=now,
        created_by=1,
        created_at=now,
    )


def _build_service(
    *,
    repo: AsyncMock | None = None,
    storage: AsyncMock | None = None,
    rabbit: MagicMock | None = None,
    settings: CreateDocumentServiceSettings | None = None,
) -> CreateDocumentService:
    repo = repo or AsyncMock()
    storage = storage or AsyncMock()
    rabbit = rabbit or _rabbit_mock()
    return CreateDocumentService(
        document_repository=repo,
        document_storage=storage,
        rabbitmq_manager=rabbit,
        create_document_service_settings=settings or CreateDocumentServiceSettings(),
    )


@pytest.mark.asyncio
async def test_happy_path_pdf_publishes_command_with_prefer_docling() -> None:
    repo = AsyncMock()
    repo.create_document = AsyncMock(return_value=_persisted_document())
    storage = AsyncMock()
    storage.upload_document = AsyncMock(return_value="obj-1")
    rabbit = _rabbit_mock()
    service = _build_service(repo=repo, storage=storage, rabbit=rabbit)
    req = CreateDocumentRequest(chat_id=7, prefer_docling=True)
    uf = make_upload_file(data=PDF_MINIMAL, filename="a.pdf", content_type=CT_PDF)
    session = MagicMock()
    session.commit = AsyncMock()

    result = await service.create_document(req, uf, session, _user())

    assert result.id == 42
    rabbit.publish.assert_awaited_once()
    kwargs = rabbit.publish.await_args.kwargs
    body = kwargs.get("body")
    assert body is not None
    env = MessageEnvelope.from_bytes(body, DocumentIngestionCommand)
    assert env.command.document_id == 42
    assert env.command.prefer_docling is True
    assert env.command.storage_url == "obj-1"
    repo.create_document.assert_awaited_once()
    storage.upload_document.assert_awaited_once()


@pytest.mark.asyncio
async def test_happy_path_docx() -> None:
    repo = AsyncMock()
    repo.create_document = AsyncMock(
        return_value=_persisted_document(name="b.docx", mime=DocumentMimeType.docx)
    )
    storage = AsyncMock()
    storage.upload_document = AsyncMock(return_value="obj-docx")
    rabbit = _rabbit_mock()
    service = _build_service(repo=repo, storage=storage, rabbit=rabbit)
    req = CreateDocumentRequest(chat_id=1, prefer_docling=False)
    uf = make_upload_file(data=DOCX_ZIP_PREFIX, filename="b.docx", content_type=CT_DOCX)
    session = MagicMock()
    session.commit = AsyncMock()

    result = await service.create_document(req, uf, session, _user())

    assert result.mime_type == DocumentMimeType.docx
    rabbit.publish.assert_awaited_once()


@pytest.mark.asyncio
async def test_missing_document_create_permission() -> None:
    service = _build_service()
    req = CreateDocumentRequest(chat_id=1, prefer_docling=False)
    uf = make_upload_file(data=PDF_MINIMAL, filename="a.pdf", content_type=CT_PDF)
    session = MagicMock()

    with pytest.raises(CreateDocumentUnauthorizedException):
        await service.create_document(
            req,
            uf,
            session,
            _user(permissions=[]),
        )


@pytest.mark.asyncio
async def test_missing_allowed_role() -> None:
    service = _build_service()
    req = CreateDocumentRequest(chat_id=1, prefer_docling=False)
    uf = make_upload_file(data=PDF_MINIMAL, filename="a.pdf", content_type=CT_PDF)
    session = MagicMock()

    with pytest.raises(CreateDocumentUnauthorizedException):
        await service.create_document(
            req,
            uf,
            session,
            _user(roles=[]),
        )


@pytest.mark.asyncio
async def test_storage_failure_maps_to_upload_exception() -> None:
    repo = AsyncMock()
    storage = AsyncMock()
    storage.upload_document = AsyncMock(side_effect=DocumentStorageException("boom"))
    service = _build_service(repo=repo, storage=storage)
    req = CreateDocumentRequest(chat_id=1, prefer_docling=False)
    uf = make_upload_file(data=PDF_MINIMAL, filename="a.pdf", content_type=CT_PDF)
    session = MagicMock()

    with pytest.raises(CreateDocumentUploadException):
        await service.create_document(req, uf, session, _user())

    repo.create_document.assert_not_awaited()


@pytest.mark.asyncio
async def test_database_failure_triggers_storage_cleanup() -> None:
    repo = AsyncMock()
    repo.create_document = AsyncMock(side_effect=DatabaseException("db down"))
    storage = AsyncMock()
    storage.upload_document = AsyncMock(return_value="obj-1")
    storage.delete_document = AsyncMock()
    service = _build_service(repo=repo, storage=storage)
    req = CreateDocumentRequest(chat_id=1, prefer_docling=False)
    uf = make_upload_file(data=PDF_MINIMAL, filename="a.pdf", content_type=CT_PDF)
    session = MagicMock()
    session.commit = AsyncMock()

    with pytest.raises(CreateDocumentPersistenceException):
        await service.create_document(req, uf, session, _user())

    storage.delete_document.assert_awaited_once_with("obj-1")


@pytest.mark.asyncio
async def test_rabbit_publish_failure() -> None:
    repo = AsyncMock()
    repo.create_document = AsyncMock(return_value=_persisted_document())
    storage = AsyncMock()
    storage.upload_document = AsyncMock(return_value="obj-1")
    rabbit = _rabbit_mock()
    rabbit.publish = AsyncMock(side_effect=RuntimeError("broker down"))
    service = _build_service(repo=repo, storage=storage, rabbit=rabbit)
    req = CreateDocumentRequest(chat_id=1, prefer_docling=False)
    uf = make_upload_file(data=PDF_MINIMAL, filename="a.pdf", content_type=CT_PDF)
    session = MagicMock()
    session.commit = AsyncMock()

    # RabbitMQPublishException is not in the service's narrow except tuple; it is wrapped.
    with pytest.raises(CreateDocumentServiceException) as excinfo:
        await service.create_document(req, uf, session, _user())
    assert excinfo.value.__cause__ is not None


@pytest.mark.asyncio
async def test_deduplication_second_upload_rejected() -> None:
    settings = CreateDocumentServiceSettings(deduplication_enabled=True)
    repo = AsyncMock()
    repo.create_document = AsyncMock(return_value=_persisted_document())
    storage = AsyncMock()
    storage.upload_document = AsyncMock(return_value="obj-1")
    rabbit = _rabbit_mock()
    service = _build_service(repo=repo, storage=storage, rabbit=rabbit, settings=settings)
    req = CreateDocumentRequest(chat_id=1, prefer_docling=False)
    session = MagicMock()
    session.commit = AsyncMock()

    uf1 = make_upload_file(data=PDF_MINIMAL, filename="a.pdf", content_type=CT_PDF)
    await service.create_document(req, uf1, session, _user())

    uf2 = make_upload_file(data=PDF_MINIMAL, filename="b.pdf", content_type=CT_PDF)
    with pytest.raises(CreateDocumentValidationException) as exc:
        await service.create_document(req, uf2, session, _user())
    assert "Duplicate" in str(exc.value)
