from fastapi import Response
from abc import ABC, abstractmethod
from sqlalchemy.orm.session import Session


class DocumentDeletionServiceInterface(ABC):
    @abstractmethod
    async def soft_delete_document(
            self,
            document_id: int,
            db: Session
    ) -> Response:
        pass

    @abstractmethod
    async def hard_delete_document(
            self,
            document_id: int,
            db: Session
    ) -> Response:
        pass
