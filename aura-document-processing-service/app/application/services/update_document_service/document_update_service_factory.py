import logging

from app.application.services.update_document_service.document_update_service import UpdateDocumentService
from app.application.services.update_document_service.interfaces.update_document_service_interface import (
    UpdateDocumentServiceInterface
)
from app.infrastructure.persistence.database.repositories.document_repository.document_repository_factory import (
    create_document_repository
)

logger = logging.getLogger(__name__)


def create_update_document_service() -> UpdateDocumentServiceInterface:
    try:
        logger.info("Creating UpdateDocumentService instance")

        document_repository = create_document_repository()

        return UpdateDocumentService(
            document_repository=document_repository
        )

    except Exception:
        logger.exception("Failed to create UpdateDocumentService")
        raise
