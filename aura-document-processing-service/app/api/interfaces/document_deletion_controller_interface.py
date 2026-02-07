from abc import ABC, abstractmethod
from sqlalchemy.orm.session import Session
from fastapi import Response

from app.application.services.document_deletion_service.interfaces.document_deletion_service_interface import (
    DocumentDeletionServiceInterface
)


class DocumentDeletionControllerInterface(ABC):
    @abstractmethod
    async def soft_delete_document(
            self,
            document_id: int,
            document_deletion_service: DocumentDeletionServiceInterface,
            db: Session
    ) -> Response:
        pass

    @abstractmethod
    async def hard_delete_document(
            self,
            document_id: int,
            document_deletion_service: DocumentDeletionServiceInterface,
            db: Session
    ) -> Response:
        pass
