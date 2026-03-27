from abc import ABC, abstractmethod
from typing import List
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
    ) -> List[Fragment]:
        pass

    @abstractmethod
    async def get_most_similar_fragments(
            self,
            query_vector: List[float],
            database_session: AsyncSession,
            k: int = 3,
            threshold: float = 0.3
    ) -> List[Fragment]:
        pass

    @abstractmethod
    async def hard_delete_fragments_by_document_id(
            self,
            document_id: int,
            database_session: AsyncSession,
    ) -> int:
        pass

    @abstractmethod
    async def soft_delete_fragments_by_document_id(
            self,
            document_id: int,
            user_id: int,
            database_session: AsyncSession,
    ) -> int:
        pass

    @abstractmethod
    async def get_fragments_missing_metadata(
            self,
            database_session: AsyncSession
    ) -> List[Fragment]:
        pass

    @abstractmethod
    async def get_fragments_missing_metadata_by_document_ids(
            self,
            document_ids: List[int],
            database_session: AsyncSession
    ) -> List[Fragment]:
        pass

    @abstractmethod
    async def update_fragment(
            self,
            fragment: Fragment,
            database_session: AsyncSession
    ) -> Fragment:
        pass
