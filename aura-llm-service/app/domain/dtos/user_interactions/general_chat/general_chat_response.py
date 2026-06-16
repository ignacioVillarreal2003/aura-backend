from pydantic import BaseModel, Field, field_validator

from app.domain.dtos.fragment.fragment_response import FragmentResponse
from app.domain.dtos.message import Message
from app.domain.field_limits import MAX_CONTENT_CHARS, MAX_MESSAGES_IN_REQUEST
from app.domain.validation import stripped_non_blank


class GeneralChatResponse(BaseModel):
    answer: str = Field(..., min_length=1, max_length=MAX_CONTENT_CHARS)
    messages: list[Message] = Field(..., min_length=1, max_length=MAX_MESSAGES_IN_REQUEST)
    fragments: list[FragmentResponse] = Field(
        default_factory=list,
        description="Fragmentos documentales utilizados como contexto.",
    )
    degraded_stages: list[str] = Field(
        default_factory=list,
        description=(
            "Etapas del pipeline de contexto que se degradaron (una dependencia falló y se "
            "continuó sin ella). Si no está vacío, la respuesta puede ser parcial."
        ),
    )

    @field_validator("answer")
    @classmethod
    def _strip_answer(cls, value: str) -> str:
        return stripped_non_blank(value, "Answer must not be blank.")

    model_config = {"from_attributes": True}
