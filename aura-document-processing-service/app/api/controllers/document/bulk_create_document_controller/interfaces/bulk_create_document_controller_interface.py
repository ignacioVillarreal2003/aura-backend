from abc import ABC, abstractmethod
from fastapi import UploadFile

from app.application.services.document.bulk_create_document_service.interfaces.bulk_create_document_service_interface import (
    BulkCreateDocumentServiceInterface,
)
from app.domain.dtos.document.create_document.create_document_request import CreateDocumentRequest
from app.domain.dtos.document.bulk_create_document.bulk_create_document_response import (
    BulkCreateDocumentResponse,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser


class BulkCreateDocumentControllerInterface(ABC):
    @abstractmethod
    async def bulk_create_documents(
            self,
            create_document_request: CreateDocumentRequest,
            files: list[UploadFile],
            bulk_create_document_service: BulkCreateDocumentServiceInterface,
            authenticated_user: AuthenticatedUser,
    ) -> BulkCreateDocumentResponse:
        pass
