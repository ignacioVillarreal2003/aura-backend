import logging

from app.application.services.document_deletion_service.document_deletion_service import (
    DocumentDeletionService
)
from app.application.services.document_deletion_service.interfaces.document_deletion_service_interface import (
    DocumentDeletionServiceInterface
)
from app.infrastructure.persistence.database.repositories.document_repository.document_repository_factory import (
    create_document_repository
)
from app.infrastructure.persistence.database.repositories.fragment_repository.fragment_repository_factory import (
    create_fragment_repository
)
from app.infrastructure.persistence.storages.document_storage.interfaces.document_storage_interface import (
    DocumentStorageInterface
)

logger = logging.getLogger(__name__)


def create_document_deletion_service(
        document_storage: DocumentStorageInterface
) -> DocumentDeletionServiceInterface:
    try:
        logger.info("Creating DocumentDeletionService instance")

        document_repository = create_document_repository()
        fragment_repository = create_fragment_repository()

        return DocumentDeletionService(
            document_repository=document_repository,
            fragment_repository=fragment_repository,
            document_storage=document_storage
        )

    except Exception as e:
        logger.exception("Failed to create DocumentDeletionService")
        raise
