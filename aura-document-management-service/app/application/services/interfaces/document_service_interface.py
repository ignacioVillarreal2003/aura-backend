from typing import Protocol
from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.domain.dtos.document_request import DocumentRequest
from app.domain.dtos.document_response import DocumentResponseSchema


class DocumentServiceInterface(Protocol):
    async def create_document(self,
                              request: DocumentRequest,
                              file: UploadFile,
                              db: Session) -> DocumentResponseSchema:
        ...