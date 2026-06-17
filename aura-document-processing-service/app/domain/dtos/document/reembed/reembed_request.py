from pydantic import BaseModel, Field

from app.domain.field_limits import MAX_ID


class ReembedRequest(BaseModel):
    document_id: int = Field(..., ge=1, le=MAX_ID, description="ID del documento a re-embeber.")
    force: bool = Field(
        default=False,
        description=(
            "Si True, re-embebe todos los fragmentos aunque ya estén en el modelo activo. "
            "Si False (default), solo re-embebe los fragmentos cuyo modelo difiere del activo."
        ),
    )

    model_config = {"extra": "forbid"}
