from pydantic import BaseModel, Field

from app.domain.field_limits import MAX_ID


class GraphReextractRequest(BaseModel):
    document_id: int = Field(..., ge=1, le=MAX_ID, description="ID del documento a re-extraer.")
    force: bool = Field(
        default=False,
        description=(
            "Si True, fuerza la extracción aunque ya exista un job en curso, "
            "liberando el lock previo. Las entidades y relaciones existentes "
            "se fusionan idempotentemente mediante MERGE."
        ),
    )

    model_config = {"extra": "forbid"}
