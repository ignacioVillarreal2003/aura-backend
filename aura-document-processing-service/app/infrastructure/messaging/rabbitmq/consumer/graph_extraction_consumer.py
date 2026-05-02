import json
import logging

import aio_pika.abc
from pydantic import ValidationError

from app.application.services.graph.graph_extraction_service.interfaces.graph_extraction_service_interface import (
    GraphExtractionServiceInterface,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.infrastructure.messaging.rabbitmq.consumer.consumer_utils import extract_retry_count
from app.infrastructure.messaging.rabbitmq.consumer.interfaces.graph_extraction_consumer_interface import (
    GraphExtractionConsumerInterface,
)
from app.infrastructure.messaging.rabbitmq.dtos.commands.graph_extraction_command import (
    GraphExtractionCommand,
)
from app.infrastructure.messaging.rabbitmq.dtos.envelope.message_envelope import MessageEnvelope
from app.infrastructure.messaging.rabbitmq.rabbitmq_manager_interface import RabbitMQManagerInterface

logger = logging.getLogger(__name__)


class GraphExtractionConsumer(GraphExtractionConsumerInterface):
    """Listens on the graph-extraction queue and runs the extraction service.

    Follows the same defensive parsing/ack/nack pattern used by
    ``PostProcessDocumentConsumer``: on parse failure or repeated delivery
    the message is nacked without requeue so it is dead-lettered. On
    handler failure the message is also nacked without requeue, allowing
    the broker's DLX to retry through the configured topology.
    """

    def __init__(
            self,
            rabbitmq_manager: RabbitMQManagerInterface,
            graph_extraction_service: GraphExtractionServiceInterface,
    ) -> None:
        self._manager = rabbitmq_manager
        self._settings = rabbitmq_manager.settings
        self._service = graph_extraction_service

    async def start(self) -> None:
        await self._manager.start_consumer(
            queue_name=self._settings.graph_extraction_queue,
            callback=self._handle_message,
            prefetch_count=1,
        )
        logger.info(
            "The graph-extraction consumer was registered on the queue.",
            extra={"queue": self._settings.graph_extraction_queue},
        )

    async def _handle_message(
            self,
            message: aio_pika.abc.AbstractIncomingMessage,
    ) -> None:
        retry_count = extract_retry_count(message)
        message_id = (message.headers or {}).get("message_id", "unknown")

        if retry_count >= self._settings.max_delivery_attempts:
            logger.error(
                "A graph-extraction message exceeded the maximum delivery attempts and will be discarded.",
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
                "The graph-extraction message body exceeded the configured maximum size; discarding without requeue.",
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
                command_type=GraphExtractionCommand,
                retry_count=retry_count,
            )
        except UnicodeDecodeError as e:
            logger.error(
                "The graph-extraction message body was not valid UTF-8; discarding without requeue.",
                extra={"message_id": message_id, "error": type(e).__name__},
            )
            await message.nack(requeue=False)
            return
        except json.JSONDecodeError as e:
            logger.error(
                "The graph-extraction message body was not valid JSON; discarding without requeue.",
                extra={"message_id": message_id, "error": type(e).__name__},
            )
            await message.nack(requeue=False)
            return
        except ValidationError as e:
            logger.error(
                "The graph-extraction envelope failed schema validation; discarding without requeue.",
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
                "The graph-extraction envelope is missing required fields; discarding without requeue.",
                extra={"message_id": message_id, "error": type(e).__name__},
            )
            await message.nack(requeue=False)
            return

        command: GraphExtractionCommand = envelope.command

        try:
            user = AuthenticatedUser.model_validate(command.user)
        except ValidationError as e:
            logger.error(
                "The graph-extraction command carries an invalid user payload; discarding without requeue.",
                extra={
                    "message_id": envelope.message_id,
                    "document_id": command.document_id,
                    "validation_error_count": len(e.errors()),
                },
            )
            await message.nack(requeue=False)
            return

        try:
            await self._service.extract_for_document(
                document_id=command.document_id,
                user=user,
                force=command.force,
                message_id=envelope.message_id,
            )
            await message.ack()
            logger.info(
                "The graph-extraction message was acknowledged.",
                extra={
                    "message_id": envelope.message_id,
                    "document_id": command.document_id,
                    "user_id": user.id,
                },
            )
        except Exception:
            logger.exception(
                "The graph-extraction handler failed; negative-acknowledging for dead-letter retry.",
                extra={
                    "message_id": envelope.message_id,
                    "document_id": command.document_id,
                    "retry_count": retry_count,
                },
            )
            await message.nack(requeue=False)
