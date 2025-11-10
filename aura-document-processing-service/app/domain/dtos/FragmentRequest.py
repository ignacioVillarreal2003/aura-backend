from fastapi import Form
from pydantic import BaseModel, Field


class FragmentRequestSchema(BaseModel):
    document_id: int = Field(...)

    @classmethod
    def as_form(
            cls,
            document_id: int = Form(...)
    ):
        return cls(document_id=document_id)