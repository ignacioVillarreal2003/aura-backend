from abc import ABC, abstractmethod
from fastapi import UploadFile

from app.domain.dtos.document.create_document.create_document_request import CreateDocumentRequest
from app.domain.dtos.document.bulk_create_document.bulk_create_document_response import (
    BulkCreateDocumentResponse,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser


class BulkCreateDocumentServiceInterface(ABC):
    @abstractmethod
    async def bulk_create_documents(
            self,
            create_document_request: CreateDocumentRequest,
            raw_documents: list[UploadFile],
            authenticated_user: AuthenticatedUser,
    ) -> BulkCreateDocumentResponse:
        pass
