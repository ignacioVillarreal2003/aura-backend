from pydantic import BaseModel, Field


class DocumentQuestionToolInput(BaseModel):
    question: str = Field(..., description="The question to answer from the document knowledge base")
