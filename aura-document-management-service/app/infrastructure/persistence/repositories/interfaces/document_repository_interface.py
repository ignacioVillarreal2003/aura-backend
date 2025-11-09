from typing import Protocol
from sqlalchemy.orm import Session

from app.domain.models.document import Document


class DocumentRepositoryInterface(Protocol):
    def create(self,
               document: Document,
               db: Session) -> Document:
        ...