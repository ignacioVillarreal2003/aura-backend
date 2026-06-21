from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.constants.document.document_type import DocumentType
from app.infrastructure.persistence.database.orm.document import Document


class DocumentRepositoryInterface(ABC):
    @abstractmethod
    async def get_document_by_id(
            self,
            document_id: int,
            database_session: AsyncSession,
    ) -> Optional[Document]:
        pass

    @abstractmethod
    async def get_document_by_id_including_deleted(
            self,
            document_id: int,
            database_session: AsyncSession,
    ) -> Optional[Document]:
        pass

    @abstractmethod
    async def get_documents_by_chat_id(
            self,
            chat_id: int,
            database_session: AsyncSession,
            page: Optional[int] = None,
            size: Optional[int] = None,
    ) -> list[Document]:
        pass

    @abstractmethod
    async def get_documents_by_ids(
            self,
            document_ids: list[int],
            database_session: AsyncSession,
    ) -> list[Document]:
        pass

    @abstractmethod
    async def get_documents(
            self,
            database_session: AsyncSession,
            page: Optional[int] = None,
            size: Optional[int] = None,
            name: Optional[str] = None,
            description: Optional[str] = None,
            category: Optional[str] = None,
            document_type: Optional[DocumentType] = None,
            created_from: Optional[datetime] = None,
            created_to: Optional[datetime] = None,
    ) -> list[Document]:
        pass

    @abstractmethod
    async def create_document(
            self,
            document: Document,
            database_session: AsyncSession,
    ) -> Document:
        pass

    @abstractmethod
    async def update_document(
            self,
            document: Document,
            database_session: AsyncSession,
    ) -> Document:
        pass

    @abstractmethod
    async def soft_delete_document_by_id(
            self,
            document_id: int,
            user_id: int,
            database_session: AsyncSession,
            deleted_at: Optional[datetime] = None,
    ) -> bool:
        pass

    @abstractmethod
    async def restore_document_by_id(
            self,
            document_id: int,
            user_id: int,
            database_session: AsyncSession,
    ) -> Optional[Document]:
        pass

    @abstractmethod
    async def get_stale_uploaded_documents(
            self,
            created_before: datetime,
            limit: int,
            database_session: AsyncSession,
    ) -> list[Document]:
        pass
