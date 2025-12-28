import logging
from typing import List

from app.application.exceptions.app_exceptions import ValidationError
from app.application.services.document_question_service.document_question_configuration import (
    DocumentQuestionConfiguration
)
from app.domain.dtos.document_question_request import DocumentQuestionRequest
from app.domain.dtos.message import Message

logger = logging.getLogger(__name__)


class DocumentQuestionRequestValidator:
    def __init__(self,
                 configuration: DocumentQuestionConfiguration):
        self._configuration = configuration

    def validate_request(self,
                         request: DocumentQuestionRequest) -> None:
        logger.debug(
            "Validating DocumentQuestionRequest",
            extra={
                "question": request.question,
                "messages": request.messages
            }
        )

        self._validate_question(request.question)

        if request.messages is not None:
            self._validate_history(request.messages)

        logger.debug("DocumentQuestionRequest validation successful")

    def _validate_question(self,
                           question: str) -> None:
        if not question or not question.strip():
            logger.error(
                "Validation failed, empty question",
                extra={
                    "question_present": bool(question)
                }
            )
            raise ValidationError(
                "Question cannot be empty",
                status_code=400
            )

        question_length = len(question.strip())

        logger.debug(
            "Validating question length",
            extra={
                "question_length": question_length,
                "min_length": self._configuration.MIN_QUESTION_LENGTH,
                "max_length": self._configuration.default_question_length,
            }
        )

        if question_length < self._configuration.MIN_QUESTION_LENGTH:
            logger.error(
                "Validation failed, question too short",
                extra={
                    "question_length": question_length,
                    "min_length": self._configuration.MIN_QUESTION_LENGTH
                }
            )
            raise ValidationError(
                f"Question is too short (minimum {self._configuration.MIN_QUESTION_LENGTH} character)",
                status_code=400
            )

        if question_length > self._configuration.default_question_length:
            logger.error(
                "Validation failed, question too long",
                extra={
                    "question_length": question_length,
                    "max_length": self._configuration.default_question_length
                }
            )
            raise ValidationError(
                f"Question is too long (maximum {self._configuration.default_question_length} characters)",
                status_code=400
            )

    def _validate_history(self,
                          messages: List[Message]) -> None:
        history_count = len(messages)

        logger.debug(
            "Validating message history",
            extra={
                "history_count": history_count,
                "min_history": self._configuration.MIN_HISTORY_COUNT,
                "max_history": self._configuration.default_history_count
            }
        )

        if history_count < self._configuration.MIN_HISTORY_COUNT:
            logger.error(
                "Validation failed, message history too short",
                extra={
                    "history_count": history_count,
                    "min_history": self._configuration.MIN_HISTORY_COUNT
                }
            )
            raise ValidationError(
                f"Message history is too short (minimum {self._configuration.MIN_HISTORY_COUNT} message)",
                status_code=400
            )

        if history_count > self._configuration.default_history_count:
            logger.error(
                "Validation failed, message history too long",
                extra={
                    "history_count": history_count,
                    "max_history": self._configuration.default_history_count
                }
            )
            raise ValidationError(
                f"Message history is too long (maximum {self._configuration.default_history_count} messages)",
                status_code=400
            )
