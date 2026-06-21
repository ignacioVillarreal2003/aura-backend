from pydantic import BaseModel, Field

from app.domain.dtos.document.bulk.document_selector import DocumentSelector


class EnrichRequest(BaseModel):
    selector: DocumentSelector = Field(...)

    model_config = {"extra": "forbid"}
