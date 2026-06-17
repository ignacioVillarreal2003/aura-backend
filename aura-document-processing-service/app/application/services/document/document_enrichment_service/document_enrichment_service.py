import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services.document.document_enrichment_service.interfaces.document_enrichment_service_interface import (
    DocumentEnrichmentServiceInterface,
)
from app.application.services.document.post_process_document_service.interfaces.post_process_document_processor_interface import (
    PostProcessDocumentProcessorInterface,
)
from app.application.services.fragment.post_process_fragment_service.interfaces.post_process_fragment_processor_interface import (
    PostProcessFragmentProcessorInterface,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.constants.processing_status import ProcessingStatus
from app.infrastructure.persistence.database.database_manager.database_manager_interface import (
    DatabaseManagerInterface,
)
from app.infrastructure.persistence.database.repositories.document_repository.document_repository_interface import (
    DocumentRepositoryInterface,
)

logger = logging.getLogger(__name__)


class DocumentEnrichmentService(DocumentEnrichmentServiceInterface):
    def __init__(
            self,
            *,
            post_process_document_processor: PostProcessDocumentProcessorInterface,
            post_process_fragment_processor: PostProcessFragmentProcessorInterface,
            database_manager: DatabaseManagerInterface,
            document_repository: DocumentRepositoryInterface,
    ) -> None:
        self._document_processor = post_process_document_processor
        self._fragment_processor = post_process_fragment_processor
        self._database_manager = database_manager
        self._document_repository = document_repository

    async def enrich_for_document(
            self,
            *,
            document_id: int,
            user: AuthenticatedUser,
    ) -> None:
        logger.info(
            "Document enrichment was initiated.",
            extra={"document_id": document_id, "user_id": user.id},
        )

        first_error: Optional[BaseException] = None

        try:
            await self._document_processor.process_document_metadata(
                document_id=document_id,
                user=user,
            )
        except Exception as e:
            first_error = e
            logger.exception(
                "Document metadata enrichment failed.",
                extra={"document_id": document_id},
            )

        try:
            await self._fragment_processor.process_document_fragments(
                document_id=document_id,
                user=user,
            )
        except Exception as e:
            first_error = first_error or e
            logger.exception(
                "Fragment enrichment failed.",
                extra={"document_id": document_id},
            )

        if first_error is not None:
            await self._set_enrichment_status(document_id, ProcessingStatus.failed)
            raise first_error

        await self._set_enrichment_status(document_id, ProcessingStatus.processed)
        logger.info(
            "Document enrichment completed successfully.",
            extra={"document_id": document_id},
        )

    async def _set_enrichment_status(
            self,
            document_id: int,
            status: ProcessingStatus,
    ) -> None:
        try:
            async def _operation(session: AsyncSession) -> None:
                document = await self._document_repository.get_document_by_id(
                    document_id=document_id,
                    database_session=session,
                )
                if document is None:
                    return
                document.enrichment_status = status
                await self._document_repository.update_document(
                    document=document,
                    database_session=session,
                )

            await self._database_manager.run_write_transaction_with_retry(
                _operation,
                operation_name="document_enrichment.set_enrichment_status",
            )
        except Exception:
            logger.warning(
                "Failed to update the document enrichment status.",
                extra={"document_id": document_id, "enrichment_status": status.value},
            )
