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
    def __init__(
            self,
            document_question_configuration: DocumentQuestionConfiguration
    ) -> None:
        self._document_question_configuration = document_question_configuration
        logger.debug("DocumentQuestionRequestValidator initialized")

    def validate_request(
            self,
            document_question_request: DocumentQuestionRequest
    ) -> None:
        logger.debug(
            "Starting request validation",
            extra={
                "question": document_question_request.question,
                "history_messages": document_question_request.history_messages if document_question_request.history_messages else None,
            }
        )

        self._validate_question(
            question=document_question_request.question
        )

        if document_question_request.history_messages is not None:
            self._validate_history_messages(document_question_request.history_messages)

        logger.debug("Request validation completed successfully")

    def _validate_question(
            self,
            question: str
    ) -> None:
        if not question or not question.strip():
            logger.warning(
                "Question validation failed: empty or whitespace-only",
                extra={
                    "question_is_none": question is None,
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
                "min_required": self._document_question_configuration.min_question_length,
                "max_allowed": self._document_question_configuration.max_question_length
            }
        )

        if question_length < self._document_question_configuration.min_question_length:
            logger.warning(
                "Question validation failed: too short",
                extra={
                    "question_length": question_length,
                    "min_question_length": self._document_question_configuration.min_question_length
                }
            )
            raise ValidationError(
                f"La pregunta es demasiado corta. "
                f"Debe tener al menos {self._document_question_configuration.min_question_length} caracteres.",
                status_code=400
            )

        if question_length > self._document_question_configuration.max_question_length:
            logger.warning(
                "Question validation failed: too long",
                extra={
                    "question_length": question_length,
                    "max_question_length": self._document_question_configuration.max_question_length
                }
            )
            raise ValidationError(
                f"La pregunta es demasiado larga. "
                f"No debe exceder {self._document_question_configuration.max_question_length} caracteres.",
                status_code=400
            )

    def _validate_history_messages(
            self,
            history_messages: List[Message]
    ) -> None:
        history_messages_count = len(history_messages)

        logger.debug(
            "Validating message history",
            extra={
                "history_messages_count": history_messages_count,
                "max_history_messages": self._document_question_configuration.max_history_messages
            }
        )

        if history_messages_count > self._document_question_configuration.max_history_messages:
            logger.warning(
                "History validation failed: too many messages",
                extra={
                    "history_messages_count": history_messages_count,
                    "max_history_messages": self._document_question_configuration.max_history_messages
                }
            )
            raise ValidationError(
                f"El historial de mensajes es demasiado largo. "
                f"Máximo permitido: {self._document_question_configuration.max_history_messages} mensajes.",
                status_code=400
            )
