from abc import ABC, abstractmethod
from datetime import datetime
from typing import Literal, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.dtos.document.document_search.document_similarity_hit import DocumentSimilarityHit
from app.infrastructure.persistence.database.orm.fragment import Fragment


class FragmentRepositoryInterface(ABC):
    @abstractmethod
    async def get_fragment_by_id(
            self,
            fragment_id: int,
            database_session: AsyncSession,
    ) -> Optional[Fragment]:
        pass

    @abstractmethod
    async def get_fragments_by_document_id(
            self,
            document_id: int,
            database_session: AsyncSession,
    ) -> list[Fragment]:
        pass

    @abstractmethod
    async def get_most_similar_fragments(
            self,
            query_vector: list[float],
            database_session: AsyncSession,
            *,
            embedding_identity: str,
            k: int = 3,
            threshold: float = 0.3,
            document_ids: list[int] | None = None,
            representation: Literal["raw", "contextual"] = "raw",
    ) -> list[Fragment]:
        pass

    @abstractmethod
    async def search_documents_by_similarity(
            self,
            query_vector: list[float],
            database_session: AsyncSession,
            k: int,
            threshold: float,
            pool_size: int,
            *,
            embedding_identity: str,
            offset: int = 0,
            document_ids: list[int] | None = None,
    ) -> list[DocumentSimilarityHit]:
        pass

    @abstractmethod
    async def search_documents_by_bm25(
            self,
            *,
            query: str,
            database_session: AsyncSession,
            k: int,
            pool_size: int,
            offset: int = 0,
            min_score: float = 0.0,
            query_max_chars: int = 512,
            document_ids: list[int] | None = None,
    ) -> list[DocumentSimilarityHit]:
        pass

    @abstractmethod
    async def get_adjacent_fragments(
            self,
            fragments: list[Fragment],
            window: int,
            database_session: AsyncSession,
            exclude_ids: set[int],
            respect_section_boundaries: bool = True,
    ) -> list[Fragment]:
        pass

    @abstractmethod
    async def get_section_fragments(
            self,
            fragments: list[Fragment],
            max_per_section: int,
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
            document_ids: list[int] | None = None,
            representation: Literal["raw", "contextual"] = "raw",
    ) -> list[Fragment]:
        pass

    @abstractmethod
    async def get_fragments_by_document_ids(
            self,
            document_ids: list[int],
            database_session: AsyncSession,
    ) -> list[Fragment]:
        pass

    @abstractmethod
    async def create_fragments(
            self,
            fragments: list[Fragment],
            database_session: AsyncSession,
    ) -> list[Fragment]:
        pass

    @abstractmethod
    async def update_fragment(
            self,
            fragment: Fragment,
            database_session: AsyncSession,
    ) -> Fragment:
        pass

    @abstractmethod
    async def soft_delete_fragments_by_document_id(
            self,
            document_id: int,
            user_id: int,
            database_session: AsyncSession,
            deleted_at: Optional[datetime] = None,
    ) -> int:
        pass

    @abstractmethod
    async def restore_fragments_by_document_id(
            self,
            document_id: int,
            user_id: int,
            database_session: AsyncSession,
            deleted_at: Optional[datetime] = None,
    ) -> int:
        pass

    @abstractmethod
    async def get_fragments_for_reembedding(
            self,
            document_id: int,
            database_session: AsyncSession,
    ) -> list[Fragment]:
        pass

    @abstractmethod
    async def update_fragment_embedding(
            self,
            *,
            fragment_id: int,
            vector: list[float],
            embedding_model: str,
            embedding_dim: int,
            embedding_identity: str,
            user_id: int,
            database_session: AsyncSession,
    ) -> None:
        pass

    @abstractmethod
    async def update_fragment_contextualization(
            self,
            *,
            fragment_id: int,
            contextualized_content: str,
            contextualized_vector: list[float],
            contextualized_embedding_identity: str,
            status: str,
            user_id: int,
            database_session: AsyncSession,
    ) -> None:
        pass

    @abstractmethod
    async def update_fragment_contextualized_embedding(
            self,
            *,
            fragment_id: int,
            contextualized_vector: list[float],
            contextualized_embedding_identity: str,
            user_id: int,
            database_session: AsyncSession,
    ) -> None:
        pass

    @abstractmethod
    async def update_fragment_contextualization_status(
            self,
            *,
            fragment_id: int,
            status: str,
            user_id: int,
            database_session: AsyncSession,
    ) -> None:
        pass
