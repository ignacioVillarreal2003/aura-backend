from pydantic import BaseModel, Field

from app.domain.dtos.document.bulk.document_selector import DocumentSelector


class EnrichRequest(BaseModel):
    """Run LLM enrichment over the existing fragments of the selected documents.

    Additive: it updates the existing fragments in place (summaries/topics/entities)
    without deleting or re-chunking. The selector chooses one document, several, or the
    whole corpus.
    """
    selector: DocumentSelector = Field(...)

    model_config = {"extra": "forbid"}
