from typing import Protocol, Optional
from sqlalchemy.orm.session import Session

from app.domain.models.fragment import Fragment


class FragmentRepositoryInterface(Protocol):
    def create(self,
               fragment: Fragment,
               db: Session) -> Fragment:
        ...

    def get_by_id(self,
                  fragment_id: int,
                  db: Session) -> Optional[Fragment]:
        ...

    def get_all(self,
                db: Session,
                skip: int,
                limit: int) -> list[Fragment]:
        ...

    def get_by_document_id(self,
                           document_id: int,
                           db: Session) -> list[Fragment]:
        ...

    def get_most_similar(self,
                         query_vector: list[float],
                         db: Session,
                         k: int,
                         threshold: float) -> list[Fragment]:
        ...

    def update(self,
               fragment: Fragment,
               db: Session) -> Fragment:
        ...

    def delete(self,
               fragment_id: int,
               db: Session) -> bool:
        ...

    def exists(self,
               fragment_id: int,
               db: Session) -> bool:
        ...
