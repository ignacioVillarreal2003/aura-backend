from typing import Protocol
from fastapi import UploadFile, BackgroundTasks
from sqlalchemy.orm.session import Session

from app.domain.dtos.document_request import DocumentRequest
from app.domain.dtos.document_response import DocumentResponseSchema


class DocumentServiceInterface(Protocol):
    async def create(self,
                     request: DocumentRequest,
                     file: UploadFile,
                     db: Session,
                     background_tasks: BackgroundTasks) -> DocumentResponseSchema:
        ...
