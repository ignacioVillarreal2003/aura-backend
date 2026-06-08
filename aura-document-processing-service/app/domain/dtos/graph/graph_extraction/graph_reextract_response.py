from pydantic import BaseModel, Field

from app.domain.field_limits import MAX_ID


class GraphReextractResponse(BaseModel):
    document_id: int = Field(..., ge=1, le=MAX_ID)
    message_id: str = Field(..., min_length=1, max_length=128)
    force: bool = Field(...)
    queued: bool = Field(
        default=True,
        description="True si el comando de extracción fue encolado exitosamente.",
    )
