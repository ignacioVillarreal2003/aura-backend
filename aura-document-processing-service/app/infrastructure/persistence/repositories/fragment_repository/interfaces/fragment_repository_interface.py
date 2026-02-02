from abc import ABC, abstractmethod
from typing import Optional
from sqlalchemy.orm.session import Session

from app.domain.models.fragment import Fragment


class FragmentRepositoryInterface(ABC):
    @abstractmethod
    def create(
            self,
            fragment: Fragment,
            db: Session
    ) -> Fragment:
        pass

    @abstractmethod
    def get_by_id(
            self,
            fragment_id: int,
            db: Session
    ) -> Optional[Fragment]:
        pass

    @abstractmethod
    def get_all(
            self,
            db: Session,
            skip: Optional[int],
            limit: Optional[int]
    ) -> list[Fragment]:
        pass

    @abstractmethod
    def get_by_document_id(
            self,
            document_id: int,
            db: Session
    ) -> list[Fragment]:
        pass

    @abstractmethod
    def get_most_similar(
            self,
            query_vector: list[float],
            db: Session,
            k: Optional[int],
            threshold: Optional[float]
    ) -> list[Fragment]:
        pass

    @abstractmethod
    def update(
            self,
            fragment: Fragment,
            db: Session
    ) -> Fragment:
        pass

    @abstractmethod
    def delete(
            self,
            fragment_id: int,
            db: Session
    ) -> bool:
        pass

    @abstractmethod
    def exists(
            self,
            fragment_id: int,
            db: Session
    ) -> bool:
        pass
