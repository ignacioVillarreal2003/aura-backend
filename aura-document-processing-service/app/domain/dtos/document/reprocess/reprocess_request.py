from pydantic import BaseModel, Field

from app.domain.field_limits import MAX_ID


class ReprocessRequest(BaseModel):
    document_id: int = Field(..., ge=1, le=MAX_ID, description="ID del documento a reprocesar.")
    prefer_docling: bool = Field(default=False)
    post_process: bool = Field(default=True)
    post_process_graph: bool = Field(default=True)

    model_config = {"extra": "forbid"}
