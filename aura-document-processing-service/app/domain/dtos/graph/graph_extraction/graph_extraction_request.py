from pydantic import BaseModel, Field

from app.domain.field_limits import MAX_ID


class ExtractKnowledgeGraphRequest(BaseModel):
    force: bool = Field(
        default=False,
        description=(
            "If True, the extraction job runs even if the document was "
            "already extracted. Existing entities/relations are merged "
            "idempotently so re-running is safe."
        ),
    )
    document_id_echo: int = Field(
        default=0,
        ge=0,
        le=MAX_ID,
        description=(
            "Optional client-provided echo of the document id; the "
            "service always uses the path parameter as the source of truth."
        ),
    )

    model_config = {"extra": "forbid"}
