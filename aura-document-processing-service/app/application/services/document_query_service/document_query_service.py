import logging
from typing import Optional, List
from sqlalchemy.orm import Session

from app.application.services.document_query_service.exceptions.document_query_service_exception import (
    DocumentNotFoundError
)
from app.application.services.document_query_service.interfaces.document_query_service_interface import (
    DocumentQueryServiceInterface
)
from app.domain.dtos.document_query.document_list_response import DocumentListResponse
from app.domain.dtos.document_query.document_response import DocumentResponse
from app.domain.models.document import Document
from app.infrastructure.persistence.repositories.document_repository.interfaces.document_repository_interface import (
    DocumentRepositoryInterface
)

logger = logging.getLogger(__name__)


class DocumentQueryService(DocumentQueryServiceInterface):
    def __init__(
            self,
            document_repository: DocumentRepositoryInterface
    ):
        self._document_repository = document_repository

        logger.info("DocumentQueryService initialized")

    async def get_document_by_id(
            self,
            document_id: int,
            db: Session
    ) -> DocumentResponse:
        document: Document = self._document_repository.get_document_by_id(
            document_id=document_id,
            db=db
        )
        if document is None:
            raise DocumentNotFoundError()
        return DocumentResponse(
            id=document.id,
            name=document.name,
            type=document.type,
            status=document.status,
            path=document.path
        )

    async def get_documents(
            self,
            page: Optional[int],
            size: Optional[int],
            db: Session
    ) -> DocumentListResponse:
        documents: List[Document] = self._document_repository.get_documents(
            page=page,
            size=size,
            db=db
        )
        document_list: List[DocumentResponse] = [
            DocumentResponse(
                id=d.id,
                name=d.name,
                type=d.type,
                status=d.status,
                path=d.path
            ) for d in documents
        ]
        return DocumentListResponse(
            documents=document_list
        )
