from fastapi import Response
from abc import ABC, abstractmethod
from sqlalchemy.orm.session import Session

from app.infrastructure.authentication_provider.dtos.authentication_response import AuthenticationResponse


class DocumentDeletionServiceInterface(ABC):
    @abstractmethod
    async def soft_delete_document(
            self,
            document_id: int,
            db: Session,
            user: AuthenticationResponse
    ) -> Response:
        pass

    @abstractmethod
    async def hard_delete_document(
            self,
            document_id: int,
            db: Session,
            user: AuthenticationResponse
    ) -> Response:
        pass
