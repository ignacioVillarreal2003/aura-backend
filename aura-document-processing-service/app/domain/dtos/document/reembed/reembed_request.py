from pydantic import BaseModel, Field

from app.domain.dtos.document.bulk.document_selector import DocumentSelector


class ReembedRequest(BaseModel):
    """Re-embed the existing fragments of the selected documents with the active model.

    The selector chooses one document, several, or the whole corpus (gradual migration).
    With ``force=False`` only fragments whose embedding identity differs from the active
    one are re-embedded (idempotent); with ``force=True`` every fragment is re-embedded.
    """
    selector: DocumentSelector = Field(...)
    force: bool = Field(default=False)

    model_config = {"extra": "forbid"}
