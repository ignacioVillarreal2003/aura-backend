from pydantic import BaseModel, Field


class DocumentQuestionToolInput(BaseModel):
    question: str = Field(
        ...,
        description="The question to answer based on document context"
    )
