from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.constants.document_type import DocumentType
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
            database_session: AsyncSession,
            page: Optional[int] = None,
            size: Optional[int] = None
    ) -> List[Document]:
        pass

    async def get_documents_by_chat_id(
            self,
            chat_id: int,
            database_session: AsyncSession
    ) -> List[Document]:
        pass

    @abstractmethod
    async def update_document(
            self,
            document: Document,
            database_session: AsyncSession
    ) -> Document:
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
    async def get_documents_missing_metadata(
            self,
            database_session: AsyncSession
    ) -> List[Document]:
        pass

    @abstractmethod
    async def search_documents(
            self,
            database_session: AsyncSession,
            page: Optional[int] = None,
            size: Optional[int] = None,
            name: Optional[str] = None,
            description: Optional[str] = None,
            category: Optional[str] = None,
            type: Optional[DocumentType] = None,
            created_from: Optional[datetime] = None,
            created_to: Optional[datetime] = None,
    ) -> List[Document]:
        pass
