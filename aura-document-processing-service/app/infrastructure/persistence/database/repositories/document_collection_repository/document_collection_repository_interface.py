from abc import ABC, abstractmethod
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession


class DocumentCollectionRepositoryInterface(ABC):
    @abstractmethod
    async def get_accessible_document_ids(
            self,
            user_id: int,
            document_ids: list[int],
            chat_id: Optional[int],
            accessible_collection_ids: frozenset[int],
            database_session: AsyncSession,
    ) -> set[int]:
        pass

    @abstractmethod
    async def list_all_accessible_document_ids(
            self,
            user_id: int,
            database_session: AsyncSession,
            accessible_collection_ids: frozenset[int],
            chat_id: Optional[int] = None,
            limit: int = 10_000,
    ) -> list[int]:
        pass
