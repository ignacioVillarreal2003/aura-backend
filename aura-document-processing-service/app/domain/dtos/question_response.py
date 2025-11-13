from typing import List
from pydantic import BaseModel, Field
from app.domain.dtos.fragment_response import FragmentResponse

class QuestionResponse(BaseModel):
    fragments: List[FragmentResponse] = Field(...)

    model_config = {
        "from_attributes": True
    }
