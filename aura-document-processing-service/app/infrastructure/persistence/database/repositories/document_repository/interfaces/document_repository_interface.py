from abc import ABC, abstractmethod
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.document import Document


class DocumentRepositoryInterface(ABC):
    @abstractmethod
    async def create_document(
            self,
            document: Document,
            database_session: AsyncSession
    ) -> Document:
        pass

    @abstractmethod
    async def get_document_by_id(
            self,
            document_id: int,
            database_session: AsyncSession
    ) -> Optional[Document]:
        pass

    @abstractmethod
    async def get_documents(
            self,
            page: Optional[int],
            size: Optional[int],
            database_session: AsyncSession
    ) -> List[Document]:
        pass

    @abstractmethod
    async def hard_delete_document_by_id(
            self,
            document_id: int,
            database_session: AsyncSession
    ) -> bool:
        pass

    @abstractmethod
    async def soft_delete_document_by_id(
            self,
            document_id: int,
            user_id: int,
            database_session: AsyncSession
    ) -> bool:
        pass

    @abstractmethod
    async def update_document(
            self,
            document: Document,
            database_session: AsyncSession
    ) -> Document:
        pass
