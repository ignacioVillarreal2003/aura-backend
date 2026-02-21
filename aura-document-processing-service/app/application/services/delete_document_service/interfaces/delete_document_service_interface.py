from abc import ABC, abstractmethod
from typing import Dict
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.authentication_provider.dtos.authentication_response import AuthenticationResponse


class DeleteDocumentServiceInterface(ABC):
    @abstractmethod
    async def hard_delete_document(
            self,
            document_id: int,
            database_session: AsyncSession,
            user: AuthenticationResponse
    ) -> None:
        pass

    @abstractmethod
    async def soft_delete_document(
            self,
            document_id: int,
            database_session: AsyncSession,
            user: AuthenticationResponse
    ) -> None:
        pass

    @abstractmethod
    def get_metrics(
            self
    ) -> Dict[str, int]:
        pass
