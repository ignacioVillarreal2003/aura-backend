import logging
from sqlalchemy.orm import Session
from starlette import status
from starlette.responses import Response

from app.application.services.document_deletion_service.exceptions.document_deletion_service_exception import (
    DocumentNotFoundError
)
from app.application.services.document_deletion_service.interfaces.document_deletion_service_interface import (
    DocumentDeletionServiceInterface
)
from app.domain.models.document import Document
from app.infrastructure.persistence.repositories.document_repository.interfaces.document_repository_interface import (
    DocumentRepositoryInterface
)
from app.infrastructure.persistence.repositories.fragment_repository.interfaces.fragment_repository_interface import (
    FragmentRepositoryInterface
)
from app.infrastructure.persistence.storages.document_storage.interfaces.document_storage_interface import (
    DocumentStorageInterface
)

logger = logging.getLogger(__name__)


class DocumentDeletionService(DocumentDeletionServiceInterface):
    def __init__(
            self,
            document_repository: DocumentRepositoryInterface,
            fragment_repository: FragmentRepositoryInterface,
            document_storage: DocumentStorageInterface
    ):
        self._document_repository = document_repository
        self._fragment_repository = fragment_repository
        self._document_storage = document_storage

        logger.info("DocumentDeletionService initialized")

    async def hard_delete_document(
            self,
            document_id: int,
            db: Session
    ) -> Response:
        document: Document = self._document_repository.get_document_by_id(
            document_id=document_id,
            db=db
        )
        if document is None:
            raise DocumentNotFoundError()
        self._fragment_repository.hard_delete_fragments_by_document_id(
            document_id=document_id,
            db=db
        )
        self._document_repository.hard_delete_document_by_id(
            document_id=document_id,
            db=db
        )
        self._document_storage.delete_document(
            document_path=document.path
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    async def soft_delete_document(
            self,
            document_id: int,
            db: Session
    ) -> Response:
        document: Document = self._document_repository.get_document_by_id(
            document_id=document_id,
            db=db
        )
        if document is None:
            raise DocumentNotFoundError()
        self._fragment_repository.soft_delete_fragments_by_document_id(
            document_id=document_id,
            db=db
        )
        self._document_repository.soft_delete_document_by_id(
            document_id=document_id
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
