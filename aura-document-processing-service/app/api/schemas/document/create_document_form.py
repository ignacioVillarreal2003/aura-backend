from typing import Optional
from fastapi import Form
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from app.domain.dtos.document.create_document.create_document_request import CreateDocumentRequest
from app.domain.types import ChatId


def parse_create_document_request(
        chat_id: Optional[int] = Form(None),
        prefer_docling: bool = Form(False),
        name: Optional[str] = Form(None),
        description: Optional[str] = Form(None),
) -> CreateDocumentRequest:
    try:
        return CreateDocumentRequest(
            chat_id=ChatId(chat_id) if chat_id is not None else None,
            prefer_docling=prefer_docling,
            name=name,
            description=description,
        )
    except ValidationError as e:
        raise RequestValidationError(errors=e.errors())
