from abc import ABC, abstractmethod
from typing import Dict
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.dtos.update_document.update_document_request import UpdateDocumentRequest
from app.domain.dtos.update_document.update_document_response import UpdateDocumentResponse
from app.infrastructure.authentication_provider.dtos.authentication_response import AuthenticationResponse


class UpdateDocumentServiceInterface(ABC):
    @abstractmethod
    async def update_document(
            self,
            document_id: int,
            update_document_request: UpdateDocumentRequest,
            database_session: AsyncSession,
            user: AuthenticationResponse
    ) -> UpdateDocumentResponse:
        pass

    @abstractmethod
    def get_metrics(
            self
    ) -> Dict[str, int]:
        pass
