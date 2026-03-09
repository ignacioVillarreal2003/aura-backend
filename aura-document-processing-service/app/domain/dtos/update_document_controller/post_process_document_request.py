from pydantic import BaseModel, Field

from app.domain.constants.document_type import DocumentType


class PostProcessDocumentRequest(BaseModel):
    description: str = Field()
    type: DocumentType = Field()
    category: str = Field()
