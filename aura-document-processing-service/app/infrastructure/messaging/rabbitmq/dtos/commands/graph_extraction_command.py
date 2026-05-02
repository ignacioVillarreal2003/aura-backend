from typing import Any
from pydantic import BaseModel, Field

from app.domain.field_limits import MAX_ID


class GraphExtractionCommand(BaseModel):
    """RabbitMQ command emitted at the end of a successful document ingestion.

    The KG extraction consumer uses ``document_id`` to load fragments and
    re-extracts them through the LLM. ``user`` carries the principal that
    triggered the ingestion so the KG extractor can call the LLM service
    using the same authentication context used during ingestion.
    """

    document_id: int = Field(..., ge=1, le=MAX_ID)
    user: dict[str, Any] = Field(...)
    force: bool = Field(default=False)

    model_config = {"frozen": True}
