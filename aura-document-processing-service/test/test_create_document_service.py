import io
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.application.services.document.create_document_service.create_document_service import (
    CreateDocumentService,
)
from app.application.services.document.create_document_service.create_document_service_settings import (
    CreateDocumentServiceSettings,
)
from app.application.services.document.create_document_service.exceptions.create_document_service_exception import (
    CreateDocumentInvalidException,
    CreateDocumentPersistenceException,
    CreateDocumentSizeExceededException,
    CreateDocumentUnsupportedTypeException,
    CreateDocumentUploadException,
    CreateDocumentValidationException,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.constants.document.document_mime_type import DocumentMimeType
from app.domain.constants.document.document_status import DocumentStatus
from app.domain.constants.processing_status import ProcessingStatus
from app.domain.dtos.document.create_document.create_document_request import CreateDocumentRequest
from app.domain.field_limits import MAX_NAME_CHARS
from app.infrastructure.messaging.rabbitmq.exceptions.rabbitmq_manager_exception import (
    RabbitMQPublishException,
)
from app.infrastructure.persistence.database.repositories.exceptions.database_exceptions import (
    DatabaseException,
)
from app.infrastructure.persistence.storages.document_storage.exceptions.document_storage_exception import (
    DocumentStorageException,
)



class _FakeUpload:
    """Minimal stand-in for Starlette's UploadFile (sync attrs + async seek/read)."""

    def __init__(self, *, filename="doc.pdf", content_type="application/pdf",
                 size=1024, header=b"%PDF-1.7\n"):
        self.filename = filename
        self.content_type = content_type
        self.size = size
        self.file = io.BytesIO(header)

    async def seek(self, offset):
        self.file.seek(offset)

    async def read(self, n=-1):
        return self.file.read(n)


def _user(user_id: int = 7) -> AuthenticatedUser:
    return AuthenticatedUser(id=user_id, email="u@test.com", roles=[], permissions=[])


def _request(**kwargs) -> CreateDocumentRequest:
    return CreateDocumentRequest(**kwargs)


def _make_service(*, repo=None, storage=None, rabbitmq=None, outbox=None, settings=None):
    return CreateDocumentService(
        document_repository=repo or AsyncMock(),
        document_storage=storage or AsyncMock(),
        rabbitmq_manager=rabbitmq or _rabbitmq(),
        outbox_lite=outbox,
        create_document_service_settings=settings or CreateDocumentServiceSettings(),
    )


def _rabbitmq():
    manager = AsyncMock()
    manager.settings = MagicMock()
    manager.settings.document_ingestion_queue = "document.ingestion"
    return manager



class TestFilenameValidation:
    def test_missing_filename_rejected(self):
        service = _make_service()
        with pytest.raises(CreateDocumentValidationException):
            service._validate_file_present(_FakeUpload(filename=""))

    @pytest.mark.parametrize("bad", ["../etc/passwd", "a/b.pdf", "a\\b.pdf"])
    def test_path_separators_rejected(self, bad):
        service = _make_service()
        with pytest.raises(CreateDocumentInvalidException):
            service._validate_filename(_FakeUpload(filename=bad))

    def test_null_byte_rejected(self):
        service = _make_service()
        with pytest.raises(CreateDocumentInvalidException):
            service._validate_filename(_FakeUpload(filename="bad\x00.pdf"))

    def test_too_long_filename_rejected(self):
        service = _make_service()
        with pytest.raises(CreateDocumentInvalidException):
            service._validate_filename(_FakeUpload(filename="a" * (MAX_NAME_CHARS + 1) + ".pdf"))

    def test_valid_filename_passes(self):
        service = _make_service()
        service._validate_filename(_FakeUpload(filename="report.pdf"))


class TestContentTypeValidation:
    def test_missing_content_type_rejected(self):
        service = _make_service()
        with pytest.raises(CreateDocumentInvalidException):
            service._validate_content_type(_FakeUpload(content_type=""))

    def test_unsupported_content_type_rejected(self):
        service = _make_service()
        with pytest.raises(CreateDocumentUnsupportedTypeException):
            service._validate_content_type(_FakeUpload(content_type="application/x-evil"))

    def test_allowed_content_type_passes(self):
        service = _make_service()
        service._validate_content_type(_FakeUpload(content_type="application/pdf"))


class TestSizeValidation:
    def test_too_small_rejected(self):
        settings = CreateDocumentServiceSettings(min_file_size_bytes=10)
        service = _make_service(settings=settings)
        with pytest.raises(CreateDocumentInvalidException):
            service._validate_size(_FakeUpload(size=5))

    def test_too_large_rejected(self):
        settings = CreateDocumentServiceSettings(max_file_size_mb=1)
        service = _make_service(settings=settings)
        with pytest.raises(CreateDocumentSizeExceededException):
            service._validate_size(_FakeUpload(size=2 * 1024 * 1024))

    def test_unknown_size_rejected(self):
        service = _make_service()
        upload = _FakeUpload(size=None)
        upload.file = MagicMock()
        upload.file.tell.side_effect = OSError("no tell")
        with pytest.raises(CreateDocumentInvalidException):
            service._validate_size(upload)


class TestMagicNumberValidation:
    async def test_matching_header_passes(self):
        service = _make_service()
        await service._validate_magic_numbers(
            _FakeUpload(content_type="application/pdf", header=b"%PDF-1.7")
        )

    async def test_mismatched_header_rejected(self):
        service = _make_service()
        with pytest.raises(CreateDocumentInvalidException):
            await service._validate_magic_numbers(
                _FakeUpload(content_type="application/pdf", header=b"NOPE1234")
            )

    async def test_content_type_without_magic_rules_is_skipped(self):
        service = _make_service()
        await service._validate_magic_numbers(
            _FakeUpload(content_type="text/plain", header=b"hello")
        )



class TestBuildDocument:
    def test_flags_map_to_processing_statuses(self):
        document = CreateDocumentService._build_document(
            create_document_request=_request(enrich=True, graph_extract=False),
            raw_document=_FakeUpload(filename="r.pdf"),
            authenticated_user=_user(),
            document_mime_type=DocumentMimeType.pdf,
            object_name="obj/key",
            file_size=2048,
        )
        assert document.status == DocumentStatus.uploaded
        assert document.enrichment_status == ProcessingStatus.pending
        assert document.graph_status == ProcessingStatus.not_required
        assert document.storage_url == "obj/key"
        assert document.file_size_bytes == 2048
        assert document.created_by == 7

    def test_name_falls_back_to_filename(self):
        document = CreateDocumentService._build_document(
            create_document_request=_request(name=None),
            raw_document=_FakeUpload(filename="original.pdf"),
            authenticated_user=_user(),
            document_mime_type=DocumentMimeType.pdf,
            object_name="obj",
            file_size=10,
        )
        assert document.name == "original.pdf"



class TestStoreObject:
    async def test_returns_object_name_on_success(self):
        storage = AsyncMock()
        storage.upload_document_from_path = AsyncMock(return_value="stored/obj")
        service = _make_service(storage=storage)

        result = await service._store_object(
            raw_document=_FakeUpload(), temp_path=MagicMock(), file_size=100
        )
        assert result == "stored/obj"

    async def test_client_error_maps_to_validation(self):
        storage = AsyncMock()
        storage.upload_document_from_path = AsyncMock(
            side_effect=DocumentStorageException("bad", status_code=400)
        )
        service = _make_service(storage=storage)
        with pytest.raises(CreateDocumentValidationException):
            await service._store_object(
                raw_document=_FakeUpload(), temp_path=MagicMock(), file_size=100
            )

    async def test_server_error_maps_to_upload(self):
        storage = AsyncMock()
        storage.upload_document_from_path = AsyncMock(
            side_effect=DocumentStorageException("boom", status_code=500)
        )
        service = _make_service(storage=storage)
        with pytest.raises(CreateDocumentUploadException):
            await service._store_object(
                raw_document=_FakeUpload(), temp_path=MagicMock(), file_size=100
            )



class TestPersistDocument:
    async def test_commits_and_returns_persisted_document(self):
        persisted = MagicMock(id=99)
        repo = AsyncMock()
        repo.create_document = AsyncMock(return_value=persisted)
        session = AsyncMock()
        service = _make_service(repo=repo)

        result = await service._persist_document(
            document=MagicMock(), object_name="obj", database_session=session
        )
        assert result is persisted
        session.commit.assert_awaited_once()

    async def test_database_error_cleans_storage_and_raises_persistence(self):
        repo = AsyncMock()
        repo.create_document = AsyncMock(side_effect=DatabaseException("dup"))
        storage = AsyncMock()
        service = _make_service(repo=repo, storage=storage)

        with pytest.raises(CreateDocumentPersistenceException):
            await service._persist_document(
                document=MagicMock(), object_name="obj", database_session=AsyncMock()
            )
        storage.delete_document.assert_awaited_once_with("obj")



class TestPublishIngestion:
    async def test_publishes_directly_when_no_outbox(self):
        rabbitmq = _rabbitmq()
        service = _make_service(rabbitmq=rabbitmq, outbox=None)

        message_id = await service._publish_ingestion(
            create_document_request=_request(),
            raw_document=_FakeUpload(),
            authenticated_user=_user(),
            database_document=MagicMock(id=5),
            object_name="obj",
            database_session=AsyncMock(),
        )
        assert isinstance(message_id, str) and message_id
        rabbitmq.publish.assert_awaited_once()
        assert rabbitmq.publish.await_args.kwargs["routing_key"] == "document.ingestion"

    async def test_uses_outbox_when_provided(self):
        rabbitmq = _rabbitmq()
        outbox = AsyncMock()
        service = _make_service(rabbitmq=rabbitmq, outbox=outbox)

        await service._publish_ingestion(
            create_document_request=_request(),
            raw_document=_FakeUpload(),
            authenticated_user=_user(),
            database_document=MagicMock(id=5),
            object_name="obj",
            database_session=AsyncMock(),
        )
        outbox.publish_or_enqueue.assert_awaited_once()
        rabbitmq.publish.assert_not_called()

    async def test_publish_failure_compensates_and_raises(self):
        rabbitmq = _rabbitmq()
        rabbitmq.publish = AsyncMock(side_effect=RuntimeError("broker down"))
        repo = AsyncMock()
        storage = AsyncMock()
        service = _make_service(rabbitmq=rabbitmq, repo=repo, storage=storage, outbox=None)
        session = AsyncMock()

        with pytest.raises(RabbitMQPublishException):
            await service._publish_ingestion(
                create_document_request=_request(),
                raw_document=_FakeUpload(),
                authenticated_user=_user(),
                database_document=MagicMock(id=5, created_by=7),
                object_name="obj",
                database_session=session,
            )
        repo.soft_delete_document_by_id.assert_awaited_once()
        storage.delete_document.assert_awaited_once_with("obj")


class TestCompensateFailedPublish:
    async def test_soft_deletes_commits_and_cleans_storage(self):
        repo = AsyncMock()
        storage = AsyncMock()
        service = _make_service(repo=repo, storage=storage)
        session = AsyncMock()

        await service._compensate_failed_publish(
            document=MagicMock(id=5, created_by=7),
            object_name="obj",
            database_session=session,
        )
        repo.soft_delete_document_by_id.assert_awaited_once()
        session.commit.assert_awaited_once()
        storage.delete_document.assert_awaited_once_with("obj")

    async def test_db_failure_still_cleans_storage(self):
        repo = AsyncMock()
        repo.soft_delete_document_by_id = AsyncMock(side_effect=RuntimeError("db gone"))
        storage = AsyncMock()
        service = _make_service(repo=repo, storage=storage)

        await service._compensate_failed_publish(
            document=MagicMock(id=5, created_by=7),
            object_name="obj",
            database_session=AsyncMock(),
        )
        storage.delete_document.assert_awaited_once_with("obj")
