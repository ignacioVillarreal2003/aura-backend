import logging
from typing import List

from app.application.exceptions.app_exceptions import ValidationError
from app.application.services.agent_service.agent_configuration import AgentConfiguration
from app.domain.dtos.agent_request import AgentRequest
from app.domain.dtos.message import Message

logger = logging.getLogger(__name__)


class AgentRequestValidator:
    def __init__(
            self,
                 agent_configuration: AgentConfiguration
    ) -> None:
        self._configuration = agent_configuration
        logger.debug("AgentRequestValidator initialized")

    def validate_request(
            self,
                         request: AgentRequest
    ) -> None:
        logger.debug(
            "Starting request validation",
            extra={
                "messages": request.messages
            }
        )

        self._validate_messages(request.messages)

        logger.debug("Request validation completed successfully")

    def _validate_messages(self,
                           messages: List[Message]) -> None:
        logger.debug(
            "Validating messages",
            extra={
                "messages": messages
            }
        )

        if len(messages) > self._configuration.max_messages_count:
            logger.warning(
                "Messages validation failed: too many messages",
                extra={
                    "messages_count": len(messages),
                    "max_messages_count": self._configuration.max_messages_count
                }
            )
            raise ValidationError(
                f"La cantidad de mensajes es demasiado grande. "
                f"Máximo permitido: {self._configuration.max_messages_count} mensajes.",
                status_code=400
            )
