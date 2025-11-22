from typing import Protocol

from app.domain.dtos.question_response import QuestionResponse


class QuestionPublisherInterface(Protocol):
    def publish_question(self,
                         question: QuestionResponse) -> None:
        ...
