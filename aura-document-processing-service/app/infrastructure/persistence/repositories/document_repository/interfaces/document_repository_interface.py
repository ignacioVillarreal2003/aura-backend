from abc import ABC, abstractmethod
from typing import Optional
from sqlalchemy.orm.session import Session

from app.domain.models.document import Document


class DocumentRepositoryInterface(ABC):
    @abstractmethod
    def create(
            self,
            document: Document,
            db: Session
    ) -> Document:
        pass

    @abstractmethod
    def get_by_id(
            self,
            document_id: int,
            db: Session
    ) -> Optional[Document]:
        pass

    @abstractmethod
    def get_all(
            self,
            db: Session,
            skip: int,
            limit: int
    ) -> list[Document]:
        pass

    @abstractmethod
    def update(
            self,
            document: Document,
            db: Session
    ) -> Document:
        pass

    @abstractmethod
    def delete(
            self,
            document_id: int,
            db: Session
    ) -> bool:
        pass

    @abstractmethod
    def exists(
            self,
            document_id: int,
            db: Session
    ) -> bool:
        pass
