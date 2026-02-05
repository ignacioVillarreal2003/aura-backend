from pydantic import BaseModel, Field


class DocumentQuestionToolInput(BaseModel):
    question: str = Field(
        ...
    )
