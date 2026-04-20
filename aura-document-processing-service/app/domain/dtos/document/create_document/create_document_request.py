from fastapi import Form
from pydantic import BaseModel, Field

MAX_ID = 2_147_483_647


class CreateDocumentRequest(BaseModel):
    chat_id: int = Field(..., gt=0, le=MAX_ID)
    prefer_docling: bool = Field(default=False)

    @classmethod
    def as_form(
            cls,
            chat_id: int = Form(...),
            prefer_docling: bool = Form(False)
    ):
        return cls(
            chat_id=chat_id,
            prefer_docling=prefer_docling
        )
