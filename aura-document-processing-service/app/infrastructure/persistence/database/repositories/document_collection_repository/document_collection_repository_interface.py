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
            database_session: AsyncSession
    ) -> set[int]:
        pass
