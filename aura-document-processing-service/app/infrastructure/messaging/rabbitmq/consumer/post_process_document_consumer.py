import json
import logging

import aio_pika.abc
from pydantic import ValidationError

from app.application.services.document.post_process_document_service.interfaces.post_process_document_processor_interface import (
    PostProcessDocumentProcessorInterface,
)
from app.infrastructure.messaging.rabbitmq.consumer.consumer_utils import extract_retry_count
from app.infrastructure.messaging.rabbitmq.consumer.interfaces.post_process_document_consumer_interface import (
    PostProcessDocumentConsumerInterface,
)
from app.infrastructure.messaging.rabbitmq.dtos.commands.post_process_document_job_command import (
    PostProcessDocumentJobCommand,
)
from app.infrastructure.messaging.rabbitmq.dtos.envelope.message_envelope import MessageEnvelope
from app.infrastructure.messaging.rabbitmq.rabbitmq_manager_interface import RabbitMQManagerInterface

logger = logging.getLogger(__name__)


class PostProcessDocumentConsumer(PostProcessDocumentConsumerInterface):
    def __init__(
            self,
            rabbitmq_manager: RabbitMQManagerInterface,
            processor: PostProcessDocumentProcessorInterface,
    ) -> None:
        self._manager = rabbitmq_manager
        self._settings = rabbitmq_manager.settings
        self._processor = processor

    async def start(
            self,
    ) -> None:
        await self._manager.start_consumer(
            queue_name=self._settings.post_process_document_queue,
            callback=self._handle_message,
            prefetch_count=1,
        )
        logger.info(
            "The document post-process consumer was registered on the queue.",
            extra={"queue": self._settings.post_process_document_queue},
        )

    async def _handle_message(
            self,
            message: aio_pika.abc.AbstractIncomingMessage,
    ) -> None:
        retry_count = extract_retry_count(message)

        if retry_count >= self._settings.max_delivery_attempts:
            logger.error(
                "A post-process message exceeded the maximum delivery attempts and will be discarded.",
                extra={
                    "retry_count": retry_count,
                    "max_delivery_attempts": self._settings.max_delivery_attempts,
                    "message_id": (message.headers or {}).get("message_id", "unknown"),
                },
            )
            await message.nack(requeue=False)
            return

        body = message.body
        body_len = len(body)
        if body_len > self._settings.max_message_body_bytes:
            logger.error(
                "The message body exceeded the configured maximum size; discarding without requeue.",
                extra={
                    "message_id": (message.headers or {}).get("message_id", "unknown"),
                    "body_bytes": body_len,
                    "max_message_body_bytes": self._settings.max_message_body_bytes,
                },
            )
            await message.nack(requeue=False)
            return

        try:
            envelope = MessageEnvelope.from_bytes(
                data=body,
                command_type=PostProcessDocumentJobCommand,
                retry_count=retry_count,
            )
        except UnicodeDecodeError as e:
            logger.error(
                "The message body was not valid UTF-8; discarding without requeue.",
                extra={
                    "message_id": (message.headers or {}).get("message_id", "unknown"),
                    "error": type(e).__name__,
                },
            )
            await message.nack(requeue=False)
            return
        except json.JSONDecodeError as e:
            logger.error(
                "The message body was not valid JSON; discarding without requeue.",
                extra={
                    "message_id": (message.headers or {}).get("message_id", "unknown"),
                    "error": type(e).__name__,
                },
            )
            await message.nack(requeue=False)
            return
        except ValidationError as e:
            logger.error(
                "The message envelope failed schema validation; discarding without requeue.",
                extra={
                    "message_id": (message.headers or {}).get("message_id", "unknown"),
                    "error": type(e).__name__,
                    "error_count": len(e.errors()),
                },
            )
            await message.nack(requeue=False)
            return
        except (KeyError, ValueError) as e:
            logger.error(
                "The message envelope is missing required fields; discarding without requeue.",
                extra={
                    "message_id": (message.headers or {}).get("message_id", "unknown"),
                    "error": type(e).__name__,
                },
            )
            await message.nack(requeue=False)
            return

        job_id = envelope.command.job_id
        try:
            await self._processor.run_job(job_id)
            await message.ack()
            logger.info(
                "The document post-process job message was acknowledged.",
                extra={"message_id": envelope.message_id, "job_id": job_id},
            )
        except Exception:
            logger.exception(
                "The document post-process job handler failed; negative-acknowledging for dead-letter retry.",
                extra={"message_id": envelope.message_id, "job_id": job_id, "retry_count": retry_count},
            )
            await message.nack(requeue=False)

