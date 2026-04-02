from fastapi import Form
from pydantic import BaseModel, Field


class CreateDocumentRequest(BaseModel):
    chat_id: int = Field(...)
    prefer_docling: bool = Field(default=False)

    @classmethod
    def as_form(
            cls,
            chat_id: int = Form(...),
            prefer_docling: bool = Form(False),
    ):
        return cls(chat_id=chat_id, prefer_docling=prefer_docling)
