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
                "question_length": len(request.question) if request.question else 0,
                "messages_count": len(request.messages) if request.messages else 0
            }
        )

        self._validate_question(request.question)

        if request.messages is not None:
            self._validate_history(request.messages)

        logger.debug("DocumentQuestionRequest validation successful")

    def _validate_question(self,
                           question: str) -> None:
        if not question or not question.strip():
            logger.warning(
                "Question validation failed: empty or whitespace-only question",
                extra={
                    "question_present": bool(question),
                    "question_length": len(question) if question else 0
                }
            )
            raise ValidationError(
                "La pregunta no puede estar vacía. Por favor, proporcione una pregunta válida.",
                status_code=400
            )

        question_length = len(question.strip())

        logger.debug(
            "Validating question length",
            extra={
                "question_length": question_length,
                "min_length": self._configuration.min_question_length,
                "max_length": self._configuration.max_question_length
            }
        )

        if question_length < self._configuration.min_question_length:
            logger.warning(
                "Question validation failed: question too short",
                extra={
                    "question_length": question_length,
                    "min_length": self._configuration.min_question_length
                }
            )
            raise ValidationError(
                f"La pregunta es demasiado corta (mínimo {self._configuration.min_question_length} caracteres)",
                status_code=400
            )

        if question_length > self._configuration.question_length:
            logger.warning(
                "Question validation failed: question too long",
                extra={
                    "question_length": question_length,
                    "max_length": self._configuration.question_length
                }
            )
            raise ValidationError(
                f"La pregunta es demasiado larga (máximo {self._configuration.question_length} caracteres)",
                status_code=400
            )

    def _validate_history(self,
                          messages: List[Message]) -> None:
        history_count = len(messages)

        logger.debug(
            "Validating message history",
            extra={
                "history_count": history_count,
                "min_history": self._configuration.min_history_count,
                "max_history": self._configuration.default_history_count
            }
        )

        if history_count < self._configuration.min_history_count:
            logger.warning(
                "History validation failed: message history too short",
                extra={
                    "history_count": history_count,
                    "min_history": self._configuration.min_history_count
                }
            )
            raise ValidationError(
                f"El historial de mensajes es demasiado corto (mínimo {self._configuration.min_history_count} mensajes)",
                status_code=400
            )

        if history_count > self._configuration.default_history_count:
            logger.warning(
                "History validation failed: message history too long",
                extra={
                    "history_count": history_count,
                    "max_history": self._configuration.default_history_count
                }
            )
            raise ValidationError(
                f"El historial de mensajes es demasiado largo (máximo {self._configuration.default_history_count} mensajes)",
                status_code=400
            )
