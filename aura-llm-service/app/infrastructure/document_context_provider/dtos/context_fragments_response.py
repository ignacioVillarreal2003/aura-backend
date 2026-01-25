from typing import List
from pydantic import BaseModel, Field, field_validator


class ContextFragmentsResponse(BaseModel):
    context_fragments: List[str] = Field(
        default_factory=list
    )

    @field_validator('context_fragments')
    @classmethod
    def validate_context_fragments_list(cls,
                                        v: List[str]) -> List[str]:
        if not isinstance(v, list):
            raise ValueError("context_fragments debe ser una lista")

        for idx, item in enumerate(v):
            if not isinstance(item, str):
                raise ValueError(
                    f"El fragmento de contexto en la posición {idx} no es una cadena de texto. "
                    f"Tipo recibido: {type(item).__name__}"
                )

        return v

    model_config = {
        "extra": "ignore"
    }
