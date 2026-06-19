from pydantic import BaseModel, Field

from app.domain.dtos.document.bulk.document_selector import DocumentSelector


class GraphReextractRequest(BaseModel):
    """Extract the knowledge graph for the selected documents (additive merge).

    The selector chooses one document, several, or the whole corpus. Existing entities
    and relations are merged idempotently (MERGE), so nothing is deleted. With
    ``force=True`` any active extraction lock is released before enqueuing.
    """
    selector: DocumentSelector = Field(...)
    force: bool = Field(default=False)

    model_config = {"extra": "forbid"}
