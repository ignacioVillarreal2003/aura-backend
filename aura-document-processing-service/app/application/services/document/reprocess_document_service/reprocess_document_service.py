import logging
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services.document.document_ingestion_service.interfaces.document_ingestion_service_interface import (
    DocumentIngestionServiceInterface,
)
from app.application.services.document.reprocess_document_service.exceptions.reprocess_document_service_exception import (
    ReprocessDocumentNotFoundException,
    ReprocessDocumentServiceException,
)
from app.application.services.document.reprocess_document_service.interfaces.reprocess_document_service_interface import (
    ReprocessDocumentServiceInterface,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.constants.document.document_status import DocumentStatus
from app.infrastructure.persistence.database.database_manager.interfaces.database_manager_interface import (
    DatabaseManagerInterface,
)
from app.infrastructure.persistence.database.repositories.exceptions.database_exceptions import DatabaseException
from app.infrastructure.persistence.database.repositories.interfaces.document_repository_interface import (
    DocumentRepositoryInterface,
)
from app.infrastructure.persistence.database.repositories.interfaces.fragment_repository_interface import (
    FragmentRepositoryInterface,
)
from app.infrastructure.persistence.storages.document_storage.interfaces.document_storage_interface import (
    DocumentStorageInterface,
)

logger = logging.getLogger(__name__)

_REPROCESS_TEMP_DIR_NAME = "doc_reprocess"


class ReprocessDocumentService(ReprocessDocumentServiceInterface):
    def __init__(
            self,
            document_repository: DocumentRepositoryInterface,
            fragment_repository: FragmentRepositoryInterface,
            document_storage: DocumentStorageInterface,
            document_ingestion_service: DocumentIngestionServiceInterface,
            database_manager: DatabaseManagerInterface,
    ) -> None:
        self._document_repository = document_repository
        self._fragment_repository = fragment_repository
        self._document_storage = document_storage
        self._document_ingestion_service = document_ingestion_service
        self._database_manager = database_manager

    async def reprocess_document(
            self,
            *,
            document_id: int,
            user: AuthenticatedUser,
            prefer_docling: bool = False,
            enrich: bool = True,
            graph_extract: bool = True,
    ) -> None:
        logger.info(
            "Document reprocess was initiated.",
            extra={"document_id": document_id, "user_id": user.id},
        )

        async with self._database_manager.session() as session:
            document = await self._document_repository.get_document_by_id(
                document_id=document_id,
                database_session=session,
            )
            if document is None:
                raise ReprocessDocumentNotFoundException(f"Document {document_id} was not found.")
            storage_url = document.storage_url
            filename = document.name

        temp_path: Optional[Path] = None
        handed_off = False
        try:
            temp_dir = Path(tempfile.gettempdir()) / _REPROCESS_TEMP_DIR_NAME
            temp_dir.mkdir(parents=True, exist_ok=True)
            temp_path = temp_dir / f"{uuid.uuid4().hex}_{Path(filename).name}"

            await self._document_storage.download_document_to_file(
                object_name=storage_url,
                file_path=str(temp_path),
            )

            await self._reset_for_reprocess(document_id=document_id, user_id=int(user.id))

            async with self._database_manager.session() as session:
                document = await self._document_repository.get_document_by_id(
                    document_id=document_id,
                    database_session=session,
                )
                if document is not None:
                    await session.refresh(document)
                    session.expunge(document)

            if document is None:
                raise ReprocessDocumentNotFoundException(
                    f"Document {document_id} disappeared during reprocess."
                )

            handed_off = True
            await self._document_ingestion_service.process_document(
                document=document,
                local_file_path=temp_path,
                user=user,
                prefer_docling=prefer_docling,
                enrich=enrich,
                graph_extract=graph_extract,
            )

            logger.info(
                "Document reprocess completed.",
                extra={"document_id": document_id},
            )

        except ReprocessDocumentServiceException:
            raise
        except DatabaseException as e:
            raise ReprocessDocumentServiceException("Failed to reset the document for reprocess.") from e
        except Exception as e:
            logger.exception(
                "An unexpected error occurred during document reprocess.",
                extra={"document_id": document_id},
            )
            raise ReprocessDocumentServiceException("Document reprocess failed.") from e
        finally:
            if temp_path is not None and not handed_off:
                try:
                    if temp_path.exists():
                        temp_path.unlink()
                except Exception:
                    logger.warning(
                        "Failed to clean up the reprocess temporary file.",
                        extra={"document_id": document_id, "path": str(temp_path)},
                    )

    async def _reset_for_reprocess(self, *, document_id: int, user_id: int) -> None:
        async def _operation(session: AsyncSession) -> None:
            await self._fragment_repository.soft_delete_fragments_by_document_id(
                document_id=document_id,
                user_id=user_id,
                database_session=session,
            )
            document = await self._document_repository.get_document_by_id(
                document_id=document_id,
                database_session=session,
            )
            if document is None:
                raise ReprocessDocumentNotFoundException(f"Document {document_id} was not found.")
            document.status = DocumentStatus.uploaded
            document.processing_finished_at = None
            document.updated_by = user_id
            document.updated_at = datetime.now(timezone.utc)
            await self._document_repository.update_document(
                document=document,
                database_session=session,
            )

        await self._database_manager.run_write_transaction_with_retry(
            _operation,
            operation_name="reprocess_document.reset_state",
        )
