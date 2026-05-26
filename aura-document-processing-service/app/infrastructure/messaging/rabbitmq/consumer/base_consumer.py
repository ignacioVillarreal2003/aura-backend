import json
import logging
from abc import ABC, abstractmethod
from typing import Generic, TypeVar

import aio_pika.abc
from pydantic import BaseModel, ValidationError

from app.infrastructure.messaging.rabbitmq.consumer.consumer_utils import extract_retry_count
from app.infrastructure.messaging.rabbitmq.dtos.envelope.message_envelope import MessageEnvelope
from app.infrastructure.messaging.rabbitmq.rabbitmq_manager_interface import RabbitMQManagerInterface

T = TypeVar("T", bound=BaseModel)

logger = logging.getLogger(__name__)


class BaseConsumer(ABC, Generic[T]):
    def __init__(self, rabbitmq_manager: RabbitMQManagerInterface) -> None:
        self._manager = rabbitmq_manager
        self._settings = rabbitmq_manager.settings

    @abstractmethod
    def _get_command_type(self) -> type[T]:
        pass

    @abstractmethod
    async def _process(self, envelope: MessageEnvelope[T]) -> None:
        pass

    async def _handle_message(self, message: aio_pika.abc.AbstractIncomingMessage) -> None:
        retry_count = extract_retry_count(message)
        message_id = (message.headers or {}).get("message_id", "unknown")

        if retry_count >= self._settings.max_delivery_attempts:
            logger.error(
                "A message exceeded the maximum delivery attempts and will be discarded.",
                extra={
                    "retry_count": retry_count,
                    "max_delivery_attempts": self._settings.max_delivery_attempts,
                    "message_id": message_id,
                },
            )
            await message.nack(requeue=False)
            return

        body = message.body
        if len(body) > self._settings.max_message_body_bytes:
            logger.error(
                "The message body exceeded the configured maximum size; discarding without requeue.",
                extra={
                    "message_id": message_id,
                    "body_bytes": len(body),
                    "max_message_body_bytes": self._settings.max_message_body_bytes,
                },
            )
            await message.nack(requeue=False)
            return

        try:
            envelope = MessageEnvelope.from_bytes(
                data=body,
                command_type=self._get_command_type(),
                retry_count=retry_count,
            )
        except UnicodeDecodeError as e:
            logger.error(
                "The message body was not valid UTF-8; discarding without requeue.",
                extra={"message_id": message_id, "error": type(e).__name__},
            )
            await message.nack(requeue=False)
            return
        except json.JSONDecodeError as e:
            logger.error(
                "The message body was not valid JSON; discarding without requeue.",
                extra={"message_id": message_id, "error": type(e).__name__},
            )
            await message.nack(requeue=False)
            return
        except ValidationError as e:
            logger.error(
                "The message envelope failed schema validation; discarding without requeue.",
                extra={
                    "message_id": message_id,
                    "error": type(e).__name__,
                    "error_count": len(e.errors()),
                },
            )
            await message.nack(requeue=False)
            return
        except (KeyError, ValueError) as e:
            logger.error(
                "The message envelope is missing required fields; discarding without requeue.",
                extra={"message_id": message_id, "error": type(e).__name__},
            )
            await message.nack(requeue=False)
            return

        try:
            await self._process(envelope)
            await message.ack()
            logger.info(
                "The queue message was processed and acknowledged.",
                extra={"message_id": envelope.message_id, "retry_count": retry_count},
            )
        except Exception:
            logger.exception(
                "The message handler failed; negative-acknowledging for dead-letter retry.",
                extra={"message_id": envelope.message_id, "retry_count": retry_count},
            )
            await message.nack(requeue=False)
