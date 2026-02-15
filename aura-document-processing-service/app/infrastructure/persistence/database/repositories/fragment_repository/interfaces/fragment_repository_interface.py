from abc import ABC, abstractmethod
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.fragment import Fragment


class FragmentRepositoryInterface(ABC):
    @abstractmethod
    async def create_fragments(
            self,
            fragments: List[Fragment],
            database_session: AsyncSession
    ) -> List[Fragment]:
        pass

    @abstractmethod
    async def get_fragments_by_document_id(
            self,
            document_id: int,
            database_session: AsyncSession
    ) -> list[Fragment]:
        pass

    @abstractmethod
    async def get_most_similar_fragments(
            self,
            query_vector: list[float],
            database_session: AsyncSession,
            k: Optional[int],
            threshold: Optional[float]
    ) -> list[Fragment]:
        pass

    @abstractmethod
    async def hard_delete_fragments_by_document_id(
            self,
            document_id: int,
            database_session: AsyncSession
    ) -> bool:
        pass

    @abstractmethod
    async def soft_delete_fragments_by_document_id(
            self,
            document_id: int,
            user_id: int,
            database_session: AsyncSession
    ) -> bool:
        pass
