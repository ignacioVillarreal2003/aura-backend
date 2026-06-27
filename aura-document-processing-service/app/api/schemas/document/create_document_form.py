from typing import Optional
from fastapi import Form
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from app.domain.dtos.document.create_document.create_document_request import CreateDocumentRequest
from app.domain.types import ChatId


def parse_create_document_request(
        chat_id: Optional[int] = Form(None),
        prefer_docling: bool = Form(True),
        enrich: bool = Form(False),
        graph_extract: bool = Form(False),
        name: Optional[str] = Form(None),
) -> CreateDocumentRequest:
    # Description is intentionally not accepted at creation: it is generated
    # automatically downstream (enrichment).
    try:
        return CreateDocumentRequest(
            chat_id=ChatId(chat_id) if chat_id is not None else None,
            prefer_docling=prefer_docling,
            enrich=enrich,
            graph_extract=graph_extract,
            name=name,
        )
    except ValidationError as e:
        raise RequestValidationError(errors=e.errors()) from e
