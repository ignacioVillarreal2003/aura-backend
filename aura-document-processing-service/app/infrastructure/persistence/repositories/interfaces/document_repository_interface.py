from typing import Protocol, Optional
from sqlalchemy.orm import Session

from app.domain.models.document import Document


class DocumentRepositoryInterface(Protocol):
    def create(self,
               document: Document,
               db: Session) -> Document:
        ...

    def get_by_id(self,
                  document_id: int,
                  db: Session) -> Optional[Document]:
        ...

    def get_all(self,
                db: Session,
                skip: int = 0,
                limit: int = 100) -> list[type[Document]]:
        ...

    def update(self, document: Document, db: Session) -> Document:
        ...

    def delete(self, document_id: int, db: Session) -> bool:
        ...

    def exists(self, document_id: int, db: Session) -> bool:
        ...