from typing import List

from app.application.exceptions.app_exceptions import ValidationError
from app.application.services.document_question_service.document_question_configuration import (
    DocumentQuestionConfiguration
)
from app.domain.dtos.document_question_request import DocumentQuestionRequest
from app.domain.dtos.message import Message


class DocumentQuestionRequestValidator:
    def __init__(self,
                 configuration: DocumentQuestionConfiguration):
        self._configuration = configuration

    def validate_request(self,
                         request: DocumentQuestionRequest) -> None:
        self._validate_question(request.question)

        if request.messages is not None:
            self._validate_history(request.messages)

    def _validate_question(self,
                           question: str) -> None:
        if not question or not question.strip():
            raise ValidationError(
                "Question cannot be empty",
                status_code=400
            )

        question_length = len(question.strip())

        if question_length < self._configuration.MIN_QUESTION_LENGTH:
            raise ValidationError(
                f"Question is too short (minimum {self._configuration.MIN_QUESTION_LENGTH} character)",
                status_code=400
            )

        if question_length > self._configuration.max_question_length:
            raise ValidationError(
                f"Question is too long (maximum {self._configuration.max_question_length} characters)",
                status_code=400
            )

    def _validate_history(self,
                          messages: List[Message]) -> None:
        history_count = len(messages)

        if history_count < self._configuration.MIN_HISTORY_COUNT:
            raise ValidationError(
                f"Message history is too short (minimum {self._configuration.MIN_HISTORY_COUNT} message)",
                status_code=400
            )

        if history_count > self._configuration.max_history_count:
            raise ValidationError(
                f"Message history is too long (maximum {self._configuration.max_history_count} messages)",
                status_code=400
            )
