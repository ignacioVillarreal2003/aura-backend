from pydantic import BaseModel, Field


class DocumentQuestionResponse(BaseModel):
    answer: str = Field(...)