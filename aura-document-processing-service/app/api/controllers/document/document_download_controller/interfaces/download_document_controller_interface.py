from abc import ABC, abstractmethod
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services.document.document_download_service.interfaces.document_download_service_interface import (
    DocumentDownloadServiceInterface,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser


class DocumentDownloadControllerInterface(ABC):
    @abstractmethod
    async def download_document(
            self,
            document_id: int,
            document_download_service: DocumentDownloadServiceInterface,
            database_session: AsyncSession,
            authenticated_user: AuthenticatedUser,
    ) -> StreamingResponse:
        pass

    @abstractmethod
    async def download_document_manage(
            self,
            document_id: int,
            document_download_service: DocumentDownloadServiceInterface,
            database_session: AsyncSession,
            authenticated_user: AuthenticatedUser,
    ) -> StreamingResponse:
        pass
