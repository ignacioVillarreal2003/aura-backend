from typing import Optional
from fastapi import Form
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from app.domain.dtos.document.create_document.create_document_request import CreateDocumentRequest
from app.domain.types import ChatId


def parse_create_document_request(
        chat_id: Optional[int] = Form(None),
        prefer_docling: bool = Form(False),
        post_process: bool = Form(True),
        post_process_graph: bool = Form(True),
        name: Optional[str] = Form(None),
        description: Optional[str] = Form(None),
) -> CreateDocumentRequest:
    try:
        return CreateDocumentRequest(
            chat_id=ChatId(chat_id) if chat_id is not None else None,
            prefer_docling=prefer_docling,
            post_process=post_process,
            post_process_graph=post_process_graph,
            name=name,
            description=description,
        )
    except ValidationError as e:
        raise RequestValidationError(errors=e.errors()) from e
