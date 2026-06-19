from abc import ABC, abstractmethod
from typing import AsyncIterator
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.authentication.authenticated_user import AuthenticatedUser


class DocumentDownloadServiceInterface(ABC):
    @abstractmethod
    async def download_document(
            self,
            document_id: int,
            database_session: AsyncSession,
            authenticated_user: AuthenticatedUser,
    ) -> tuple[AsyncIterator[bytes], str, str]:
        pass

    @abstractmethod
    async def download_document_manage(
            self,
            document_id: int,
            database_session: AsyncSession,
            authenticated_user: AuthenticatedUser,
    ) -> tuple[AsyncIterator[bytes], str, str]:
        pass
