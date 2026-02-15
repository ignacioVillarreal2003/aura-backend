from abc import ABC, abstractmethod
from typing import Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.dtos.document_query.document_list_response import DocumentListResponse
from app.domain.dtos.document_query.document_response import DocumentResponse
from app.infrastructure.authentication_provider.dtos.authentication_response import AuthenticationResponse


class DocumentQueryServiceInterface(ABC):
    @abstractmethod
    async def get_document_by_id(
            self,
            document_id: int,
            database_session: AsyncSession,
            user: AuthenticationResponse
    ) -> DocumentResponse:
        pass

    @abstractmethod
    async def get_documents(
            self,
            page: Optional[int],
            size: Optional[int],
            database_session: AsyncSession,
            user: AuthenticationResponse
    ) -> DocumentListResponse:
        pass

    @abstractmethod
    def get_metrics(
            self
    ) -> Dict[str, int]:
        pass
