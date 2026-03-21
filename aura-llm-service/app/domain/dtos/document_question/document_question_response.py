from pydantic import BaseModel, Field


class DocumentQuestionResponse(BaseModel):
    answer: str = Field(...)

    model_config = {
        "from_attributes": True
    }
