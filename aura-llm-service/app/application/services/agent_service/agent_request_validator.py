import logging
from typing import List

from app.application.exceptions.app_exceptions import ValidationError
from app.application.services.agent_service.agent_configuration import AgentConfiguration
from app.domain.dtos.agent_request import AgentRequest
from app.domain.dtos.message import Message

logger = logging.getLogger(__name__)


class AgentRequestValidator:
    def __init__(self,
                 configuration: AgentConfiguration) -> None:
        self._configuration = configuration
        logger.debug("AgentRequestValidator initialized")

    def validate_request(self,
                         request: AgentRequest) -> None:
        logger.debug(
            "Starting request validation",
            extra={
                "question": request.message,
                "history_messages": request.history_messages if request.history_messages else None,
            }
        )

        self._validate_message(request.question)

        if request.history_messages is not None:
            self._validate_history_messages(request.history_messages)

        logger.debug("Request validation completed successfully")

    def _validate_message(self,
                          message: str) -> None:
        if not message or not message.strip():
            logger.warning(
                "Question validation failed: empty or whitespace-only",
                extra={
                    "message_is_none": message is None,
                    "message_length": len(message) if message else 0
                }
            )
            raise ValidationError(
                "La pregunta no puede estar vacía. Por favor, proporcione una pregunta válida.",
                status_code=400
            )

        message_length = len(message.strip())

        logger.debug(
            "Validating message length",
            extra={
                "message_length": message_length,
                "min_required": self._configuration.min_message_length,
                "max_allowed": self._configuration.max_message_length
            }
        )

        if message_length < self._configuration.min_message_length:
            logger.warning(
                "Message validation failed: too short",
                extra={
                    "message_length": message_length,
                    "min_message_length": self._configuration.min_message_length
                }
            )
            raise ValidationError(
                f"La pregunta es demasiado corta. "
                f"Debe tener al menos {self._configuration.min_message_length} caracteres.",
                status_code=400
            )

        if message_length > self._configuration.max_message_length:
            logger.warning(
                "Message validation failed: too long",
                extra={
                    "message_length": message_length,
                    "max_message_length": self._configuration.max_message_length
                }
            )
            raise ValidationError(
                f"La pregunta es demasiado larga. "
                f"No debe exceder {self._configuration.max_message_length} caracteres.",
                status_code=400
            )

    def _validate_history_messages(self,
                                   history_messages: List[Message]) -> None:
        history_messages_count = len(history_messages)

        logger.debug(
            "Validating message history",
            extra={
                "history_messages_count": history_messages_count,
                "max_history_messages_count": self._configuration.max_history_messages_count
            }
        )

        if history_messages_count > self._configuration.max_history_messages_count:
            logger.warning(
                "History validation failed: too many messages",
                extra={
                    "history_messages_count": history_messages_count,
                    "max_history_messages_count": self._configuration.max_history_messages_count
                }
            )
            raise ValidationError(
                f"El historial de mensajes es demasiado largo. "
                f"Máximo permitido: {self._configuration.max_history_messages_count} mensajes.",
                status_code=400
            )
