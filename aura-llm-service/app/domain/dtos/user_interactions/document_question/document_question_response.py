from pydantic import BaseModel, Field, model_validator

from app.domain.dtos.message import Message
from app.domain.field_limits import MAX_QUESTION_CHARS, MAX_CONTENT_CHARS, MAX_MESSAGES_IN_REQUEST
from app.infrastructure.http.document_context_provider.dtos.fragment_response import FragmentResponse


class DocumentQuestionResponse(BaseModel):
    question: str = Field(..., min_length=1, max_length=MAX_QUESTION_CHARS)
    answer: str = Field(..., min_length=1, max_length=MAX_CONTENT_CHARS)
    messages: list[Message] = Field(..., min_length=1, max_length=MAX_MESSAGES_IN_REQUEST)
    fragments: list[FragmentResponse] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_response(self) -> "DocumentQuestionResponse":
        question = self.question.strip()
        if not question:
            raise ValueError("Question must not be blank.")
        answer = self.answer.strip()
        if not answer:
            raise ValueError("Answer must not be blank.")
        updates = {}
        if question != self.question:
            updates["question"] = question
        if answer != self.answer:
            updates["answer"] = answer
        if updates:
            return self.model_copy(update=updates)
        return self

    model_config = {
        "from_attributes": True
    }
