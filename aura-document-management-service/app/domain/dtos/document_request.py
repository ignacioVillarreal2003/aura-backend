from fastapi import Form
from pydantic import BaseModel, Field


class DocumentRequest(BaseModel):
    chat_id: int = Field(...)

    @classmethod
    def as_form(cls,
                chat_id: int = Form(...)):
        return cls(chat_id=chat_id)