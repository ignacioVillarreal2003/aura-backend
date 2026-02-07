from abc import ABC, abstractmethod
from typing import Optional
from sqlalchemy.orm.session import Session

from app.domain.models.document import Document


class DocumentRepositoryInterface(ABC):
    @abstractmethod
    def create_document(
            self,
            document: Document,
            db: Session
    ) -> Document:
        pass

    @abstractmethod
    def get_document_by_id(
            self,
            document_id: int,
            db: Session
    ) -> Optional[Document]:
        pass

    @abstractmethod
    def get_documents(
            self,
            page: Optional[int],
            size: Optional[int],
            db: Session
    ) -> list[Document]:
        pass

    @abstractmethod
    def hard_delete_document_by_id(
            self,
            document_id: int,
            db: Session
    ) -> bool:
        pass

    @abstractmethod
    def soft_delete_document_by_id(
            self,
            document_id: int,
            db: Session
    ) -> bool:
        pass

    @abstractmethod
    def update_document(
            self,
            document: Document,
            db: Session
    ) -> Document:
        pass
