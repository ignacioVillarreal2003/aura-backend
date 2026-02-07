from abc import ABC, abstractmethod
from typing import Optional, List
from sqlalchemy.orm.session import Session

from app.domain.models.fragment import Fragment


class FragmentRepositoryInterface(ABC):
    @abstractmethod
    def create_fragments(
            self,
            fragments: List[Fragment],
            db: Session
    ) -> List[Fragment]:
        pass

    @abstractmethod
    def get_fragments_by_document_id(
            self,
            document_id: int,
            db: Session
    ) -> list[Fragment]:
        pass

    @abstractmethod
    def get_most_similar_fragments(
            self,
            query_vector: list[float],
            db: Session,
            k: Optional[int],
            threshold: Optional[float]
    ) -> list[Fragment]:
        pass

    @abstractmethod
    def hard_delete_fragments_by_document_id(
            self,
            document_id: int,
            db: Session
    ) -> bool:
        pass

    @abstractmethod
    def soft_delete_fragments_by_document_id(
            self,
            document_id: int,
            db: Session
    ) -> bool:
        pass
