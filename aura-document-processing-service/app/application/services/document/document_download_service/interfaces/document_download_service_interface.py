from abc import ABC, abstractmethod
from typing import AsyncIterator

from app.domain.authentication.authenticated_user import AuthenticatedUser


class DocumentDownloadServiceInterface(ABC):
    @abstractmethod
    async def download_document(
            self,
            document_id: int,
            authenticated_user: AuthenticatedUser,
    ) -> tuple[AsyncIterator[bytes], str, str]:
        pass

    @abstractmethod
    async def download_document_manage(
            self,
            document_id: int,
            authenticated_user: AuthenticatedUser,
    ) -> tuple[AsyncIterator[bytes], str, str]:
        pass
