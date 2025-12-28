from typing import List

from app.application.exceptions.app_exceptions import ValidationError
from app.domain.dtos.agent_request import AgentRequest
from app.domain.dtos.message import Message


class AgentRequestValidator:
    MIN_MESSAGE_LENGTH = 1
    MAX_MESSAGE_LENGTH = 5000
    MAX_HISTORY_SIZE = 20

    @classmethod
    def validate_request(cls, request: AgentRequest) -> None:
        cls._validate_message(request.message)

        if request.messages is not None:
            cls._validate_history(request.messages)

    @classmethod
    def _validate_message(cls, message: str) -> None:
        if not message or not message.strip():
            raise ValidationError(
                "Message cannot be empty",
                status_code=400
            )

        message_length = len(message)

        if message_length < cls.MIN_MESSAGE_LENGTH:
            raise ValidationError(
                f"Message is too short (minimum {cls.MIN_MESSAGE_LENGTH} character)",
                status_code=400
            )

        if message_length > cls.MAX_MESSAGE_LENGTH:
            raise ValidationError(
                f"Message is too long (maximum {cls.MAX_MESSAGE_LENGTH} characters)",
                status_code=400
            )

    @classmethod
    def _validate_history(cls, messages: List[Message]) -> None:
        if len(messages) > cls.MAX_HISTORY_SIZE:
            raise ValidationError(
                f"History is too long (maximum {cls.MAX_HISTORY_SIZE} messages)",
                status_code=400
            )
