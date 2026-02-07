from abc import ABC, abstractmethod
from typing import Optional
from sqlalchemy.orm.session import Session

from app.domain.dtos.document_query.document_list_response import DocumentListResponse
from app.domain.dtos.document_query.document_response import DocumentResponse


class DocumentQueryServiceInterface(ABC):
    @abstractmethod
    async def get_document_by_id(
            self,
            document_id: int,
            db: Session
    ) -> DocumentResponse:
        pass

    @abstractmethod
    async def get_documents(
            self,
            page: Optional[int],
            size: Optional[int],
            db: Session
    ) -> DocumentListResponse:
        pass
