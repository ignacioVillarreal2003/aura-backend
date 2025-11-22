from typing import Protocol
from fastapi import UploadFile, BackgroundTasks
from sqlalchemy.orm.session import Session

from app.application.services.document_service import DocumentService
from app.domain.dtos.document_request import DocumentRequest
from app.domain.dtos.document_response import DocumentResponseSchema


class DocumentControllerInterface(Protocol):
    async def create(self,
                     background_tasks: BackgroundTasks,
                     request: DocumentRequest,
                     file: UploadFile,
                     document_service: DocumentService,
                     db: Session) -> DocumentResponseSchema:
        ...
