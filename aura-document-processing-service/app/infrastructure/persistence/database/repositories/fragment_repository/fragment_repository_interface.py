from abc import ABC, abstractmethod
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.persistence.database.orm.fragment import Fragment


class FragmentRepositoryInterface(ABC):
    @abstractmethod
    async def count_fragments_missing_metadata(
            self,
            database_session: AsyncSession
    ) -> int:
        pass

    @abstractmethod
    async def count_fragments_missing_metadata_by_document_ids(
            self,
            document_ids: list[int],
            database_session: AsyncSession
    ) -> int:
        pass

    @abstractmethod
    async def get_fragment_by_id(
            self,
            fragment_id: int,
            database_session: AsyncSession
    ) -> Optional[Fragment]:
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
            k: int = 3,
            threshold: float = 0.3,
            document_ids: list[int] | None = None,
    ) -> list[Fragment]:
        pass

    @abstractmethod
    async def get_adjacent_fragments(
            self,
            fragments: list[Fragment],
            window: int,
            database_session: AsyncSession,
            exclude_ids: set[int],
    ) -> list[Fragment]:
        pass

    @abstractmethod
    async def get_most_relevant_fragments_bm25(
            self,
            *,
            query: str,
            database_session: AsyncSession,
            k: int,
            min_score: float = 0.0,
            query_max_chars: int = 512,
    ) -> list[Fragment]:
        pass

    @abstractmethod
    async def get_fragments_by_document_ids(
            self,
            document_ids: list[int],
            database_session: AsyncSession
    ) -> list[Fragment]:
        pass

    @abstractmethod
    async def get_fragment_ids_missing_metadata(
            self,
            database_session: AsyncSession,
            limit: int,
            last_fragment_id: Optional[int] = None
    ) -> list[int]:
        pass

    @abstractmethod
    async def get_fragment_ids_missing_metadata_by_document_ids(
            self,
            document_ids: list[int],
            database_session: AsyncSession,
            limit: int,
            last_fragment_id: Optional[int] = None
    ) -> list[int]:
        pass

    @abstractmethod
    async def create_fragments(
            self,
            fragments: list[Fragment],
            database_session: AsyncSession
    ) -> list[Fragment]:
        pass

    @abstractmethod
    async def update_fragment(
            self,
            fragment: Fragment,
            database_session: AsyncSession
    ) -> Fragment:
        pass

    @abstractmethod
    async def soft_delete_fragments_by_document_id(
            self,
            document_id: int,
            user_id: int,
            database_session: AsyncSession
    ) -> int:
        pass
