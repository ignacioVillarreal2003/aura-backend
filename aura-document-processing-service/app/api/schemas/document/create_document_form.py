from fastapi import Form

from app.domain.dtos.document.create_document.create_document_request import CreateDocumentRequest
from app.domain.types import ChatId


def parse_create_document_request(
        chat_id: int = Form(...),
        prefer_docling: bool = Form(False),
) -> CreateDocumentRequest:
    return CreateDocumentRequest(
        chat_id=ChatId(chat_id),
        prefer_docling=prefer_docling,
    )
