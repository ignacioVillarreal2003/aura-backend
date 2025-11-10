from typing import Protocol
from sqlalchemy.orm import Session

from app.domain.models.document import Document


class DocumentRepositoryInterface(Protocol):
    def get_by_id(self,
               document_id: int,
               db: Session) -> Document:
        ...