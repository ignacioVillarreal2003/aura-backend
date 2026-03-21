import logging
from typing import List

from app.application.exceptions.app_exception import RequestValidationException
from app.application.services.document_question_service.document_question_settings import (
    DocumentQuestionServiceSettings
)
from app.domain.dtos.document_question.document_question_request import DocumentQuestionRequest
from app.domain.dtos.message import Message

logger = logging.getLogger(__name__)


class DocumentQuestionRequestValidator:
    def __init__(self, document_question_service_settings: DocumentQuestionServiceSettings) -> None:
        self._settings = document_question_service_settings

    def validate_request(self, document_question_request: DocumentQuestionRequest) -> None:
        logger.debug("Starting request validation")

        self._validate_question(question=document_question_request.question)

        if document_question_request.history_messages is not None:
            self._validate_history_messages(document_question_request.history_messages)

        logger.debug("Request validation completed successfully")

    def _validate_question(self, question: str) -> None:
        if not question or not question.strip():
            logger.warning("Question validation failed: empty or whitespace-only")
            raise RequestValidationException(
                "La pregunta no puede estar vacía. Por favor, proporcione una pregunta válida.",
                status_code=400
            )

        question_length = len(question.strip())

        if question_length < self._settings.min_question_length:
            logger.warning(
                "Question validation failed: too short",
                extra={
                    "question_length": question_length,
                    "min_question_length": self._settings.min_question_length
                }
            )
            raise RequestValidationException(
                f"La pregunta es demasiado corta. "
                f"Debe tener al menos {self._settings.min_question_length} caracteres.",
                status_code=400
            )

        if question_length > self._settings.max_question_length:
            logger.warning(
                "Question validation failed: too long",
                extra={
                    "question_length": question_length,
                    "max_question_length": self._settings.max_question_length,
                },
            )
            raise RequestValidationException(
                f"La pregunta es demasiado larga. "
                f"No debe exceder {self._settings.max_question_length} caracteres.",
                status_code=400
            )

    def _validate_history_messages(self, history_messages: List[Message]) -> None:
        count = len(history_messages)

        if count > self._settings.max_history_messages:
            logger.warning(
                "History validation failed: too many messages",
                extra={
                    "history_messages_count": count,
                    "max_history_messages": self._settings.max_history_messages
                }
            )
            raise RequestValidationException(
                f"El historial de mensajes es demasiado largo. "
                f"Máximo permitido: {self._settings.max_history_messages} mensajes.",
                status_code=400
            )
