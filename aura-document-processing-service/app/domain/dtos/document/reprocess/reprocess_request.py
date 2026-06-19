from pydantic import BaseModel, Field

from app.domain.dtos.document.bulk.document_selector import DocumentSelector


class ReprocessRequest(BaseModel):
    """Reprocess the selected documents end-to-end from their stored objects.

    The selector chooses one document, several, or the whole corpus. Each document's
    existing fragments are soft-deleted and replaced by re-running the full ingestion
    pipeline (re-download, re-chunk, re-embed).
    """
    selector: DocumentSelector = Field(...)
    prefer_docling: bool = Field(default=False)
    post_process: bool = Field(default=True)
    post_process_graph: bool = Field(default=True)

    model_config = {"extra": "forbid"}
