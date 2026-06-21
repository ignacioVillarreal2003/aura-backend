from pydantic import BaseModel, Field

from app.domain.dtos.document.bulk.document_selector import DocumentSelector


class ReprocessRequest(BaseModel):
    selector: DocumentSelector = Field(...)
    prefer_docling: bool = Field(default=True)
    enrich: bool = Field(default=False)
    graph_extract: bool = Field(default=False)

    model_config = {"extra": "forbid"}
