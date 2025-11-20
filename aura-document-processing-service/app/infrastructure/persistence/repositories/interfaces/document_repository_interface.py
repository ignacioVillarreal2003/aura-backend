from typing import Protocol, Optional
from sqlalchemy.orm.session import Session

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
                skip: int,
                limit: int) -> list[Document]:
        ...

    def update(self,
               document: Document,
               db: Session) -> Document:
        ...

    def delete(self,
               document_id: int,
               db: Session) -> bool:
        ...

    def exists(self,
               document_id: int,
               db: Session) -> bool:
        ...