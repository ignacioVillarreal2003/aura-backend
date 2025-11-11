from typing import Protocol, Optional
from sqlalchemy.orm import Session

from app.domain.models.fragment import Fragment


class FragmentRepositoryInterface(Protocol):
    def create(self, fragment: Fragment, db: Session) -> Fragment:
        ...

    def get_by_id(self, fragment_id: int, db: Session) -> Optional[Fragment]:
        ...

    def get_all(self, db: Session, skip: int = 0, limit: int = 100) -> list[type[Fragment]]:
        ...

    def get_by_document_id(self, document_id: int, db: Session) -> list[type[Fragment]]:
        ...

    def update(self, fragment: Fragment, db: Session) -> Fragment:
        ...

    def delete(self, fragment_id: int, db: Session) -> bool:
        ...

    def exists(self, fragment_id: int, db: Session) -> bool:
        ...