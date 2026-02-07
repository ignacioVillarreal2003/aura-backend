from abc import ABC, abstractmethod
from typing import Optional
from sqlalchemy.orm.session import Session

from app.application.services.document_query_service.interfaces.document_query_service_interface import (
    DocumentQueryServiceInterface
)
from app.domain.dtos.document_query.document_list_response import DocumentListResponse
from app.domain.dtos.document_query.document_response import DocumentResponse


class DocumentQueryControllerInterface(ABC):
    @abstractmethod
    async def get_document_by_id(
            self,
            document_id: int,
            document_query_service: DocumentQueryServiceInterface,
            db: Session
    ) -> DocumentResponse:
        pass

    @abstractmethod
    async def get_documents(
            self,
            page: Optional[int],
            size: Optional[int],
            document_query_service: DocumentQueryServiceInterface,
            db: Session
    ) -> DocumentListResponse:
        pass
