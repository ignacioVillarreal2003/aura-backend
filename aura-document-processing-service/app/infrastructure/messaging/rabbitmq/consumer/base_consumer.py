import json
import logging
import time
from abc import ABC, abstractmethod
from typing import Generic, Optional, TypeVar
import aio_pika.abc
import redis.asyncio as aioredis
from pydantic import BaseModel, ValidationError

from app.configuration.metrics import (
    message_processing_duration_seconds,
    messages_consumed_total,
)
from app.infrastructure.http.authentication_provider.request_token import get_request_token, set_request_token
from app.infrastructure.messaging.rabbitmq.consumer.consumer_utils import RETRY_COUNT_HEADER, extract_retry_count
from app.infrastructure.messaging.rabbitmq.dtos.envelope.message_envelope import MessageEnvelope
from app.infrastructure.messaging.rabbitmq.interfaces.rabbitmq_manager_interface import RabbitMQManagerInterface

T = TypeVar("T", bound=BaseModel)

logger = logging.getLogger(__name__)


class BaseConsumer(ABC, Generic[T]):
    def __init__(
            self,
            rabbitmq_manager: RabbitMQManagerInterface,
            dedup_redis: Optional[aioredis.Redis] = None,
    ) -> None:
        self._manager = rabbitmq_manager
        self._settings = rabbitmq_manager.settings
        self._dedup_redis = dedup_redis

    def _dedup_key(self, message_id: str) -> str:
        return f"{self._settings.consumed_marker_key_prefix}:{self._queue_name}:{message_id}"

    async def _already_consumed(self, message_id: str) -> bool:
        if self._dedup_redis is None or not message_id or message_id == "unknown":
            return False
        try:
            return bool(await self._dedup_redis.exists(self._dedup_key(message_id)))
        except Exception:
            logger.warning(
                "Dedup lookup failed; proceeding without dedup.",
                extra={"queue": self._queue_name, "message_id": message_id},
                exc_info=True,
            )
            return False

    async def _mark_consumed(self, message_id: str) -> None:
        if self._dedup_redis is None or not message_id or message_id == "unknown":
            return
        try:
            await self._dedup_redis.set(
                self._dedup_key(message_id),
                "1",
                ex=self._settings.consumed_dedup_ttl_seconds,
            )
        except Exception:
            logger.warning(
                "Dedup marking failed; a redelivery of this message may be reprocessed.",
                extra={"queue": self._queue_name, "message_id": message_id},
                exc_info=True,
            )

    @property
    @abstractmethod
    def _queue_name(self) -> str:
        pass

    @property
    def _prefetch_count(self) -> Optional[int]:
        return None

    @abstractmethod
    def _get_command_type(self) -> type[T]:
        pass

    @abstractmethod
    async def _process(self, envelope: MessageEnvelope[T]) -> None:
        pass

    async def start(self) -> None:
        await self._manager.start_consumer(
            queue_name=self._queue_name,
            callback=self._handle_message,
            prefetch_count=self._prefetch_count,
        )
        logger.info(
            "The consumer was registered on the queue.",
            extra={"queue": self._queue_name, "prefetch_count": self._prefetch_count},
        )

    async def _handle_message(self, message: aio_pika.abc.AbstractIncomingMessage) -> None:
        retry_count = extract_retry_count(message)
        message_id = (message.headers or {}).get("message_id", "unknown")

        if retry_count >= self._settings.max_delivery_attempts:
            logger.error(
                "A message exceeded the maximum delivery attempts and will be discarded.",
                extra={
                    "queue": self._queue_name,
                    "retry_count": retry_count,
                    "max_delivery_attempts": self._settings.max_delivery_attempts,
                    "message_id": message_id,
                },
            )
            messages_consumed_total.labels(queue=self._queue_name, result="dropped").inc()
            await message.nack(requeue=False)
            return

        body = message.body
        if len(body) > self._settings.max_message_body_bytes:
            logger.error(
                "The message body exceeded the configured maximum size; discarding without requeue.",
                extra={
                    "queue": self._queue_name,
                    "message_id": message_id,
                    "body_bytes": len(body),
                    "max_message_body_bytes": self._settings.max_message_body_bytes,
                },
            )
            messages_consumed_total.labels(queue=self._queue_name, result="dropped").inc()
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
                extra={"queue": self._queue_name, "message_id": message_id, "error": type(e).__name__},
            )
            messages_consumed_total.labels(queue=self._queue_name, result="dropped").inc()
            await message.nack(requeue=False)
            return
        except json.JSONDecodeError as e:
            logger.error(
                "The message body was not valid JSON; discarding without requeue.",
                extra={"queue": self._queue_name, "message_id": message_id, "error": type(e).__name__},
            )
            messages_consumed_total.labels(queue=self._queue_name, result="dropped").inc()
            await message.nack(requeue=False)
            return
        except ValidationError as e:
            logger.error(
                "The message envelope failed schema validation; discarding without requeue.",
                extra={
                    "queue": self._queue_name,
                    "message_id": message_id,
                    "error": type(e).__name__,
                    "error_count": len(e.errors()),
                },
            )
            messages_consumed_total.labels(queue=self._queue_name, result="dropped").inc()
            await message.nack(requeue=False)
            return
        except (KeyError, ValueError) as e:
            logger.error(
                "The message envelope is missing required fields; discarding without requeue.",
                extra={"queue": self._queue_name, "message_id": message_id, "error": type(e).__name__},
            )
            messages_consumed_total.labels(queue=self._queue_name, result="dropped").inc()
            await message.nack(requeue=False)
            return

        if await self._already_consumed(envelope.message_id):
            logger.info(
                "Skipping an already-consumed message (duplicate delivery).",
                extra={"queue": self._queue_name, "message_id": envelope.message_id},
            )
            messages_consumed_total.labels(queue=self._queue_name, result="duplicate").inc()
            await message.ack()
            return

        previous_token = get_request_token()
        set_request_token(getattr(envelope.command, "auth_token", None))
        start = time.perf_counter()
        try:
            await self._process(envelope)
            await self._mark_consumed(envelope.message_id)
            await message.ack()
            messages_consumed_total.labels(queue=self._queue_name, result="ack").inc()
            logger.info(
                "The queue message was processed and acknowledged.",
                extra={
                    "queue": self._queue_name,
                    "message_id": envelope.message_id,
                    "retry_count": retry_count,
                },
            )
        except Exception:
            logger.exception(
                "The message handler failed.",
                extra={
                    "queue": self._queue_name,
                    "message_id": envelope.message_id,
                    "retry_count": retry_count,
                },
            )
            await self._handle_processing_failure(message, envelope, retry_count)
        finally:
            message_processing_duration_seconds.labels(queue=self._queue_name).observe(
                time.perf_counter() - start
            )
            set_request_token(previous_token)

    async def _handle_processing_failure(
            self,
            message: aio_pika.abc.AbstractIncomingMessage,
            envelope: MessageEnvelope[T],
            retry_count: int,
    ) -> None:
        next_attempt = retry_count + 1
        if next_attempt >= self._settings.max_delivery_attempts:
            messages_consumed_total.labels(queue=self._queue_name, result="dropped").inc()
            logger.error(
                "The message exhausted its delivery attempts; sending to the dead-letter queue.",
                extra={
                    "queue": self._queue_name,
                    "message_id": envelope.message_id,
                    "retry_count": retry_count,
                    "max_delivery_attempts": self._settings.max_delivery_attempts,
                },
            )
            await message.nack(requeue=False)
            return

        try:
            headers = dict(message.headers or {})
            headers[RETRY_COUNT_HEADER] = next_attempt
            headers["message_id"] = envelope.message_id
            await self._manager.publish(
                routing_key=self._queue_name,
                body=message.body,
                exchange_name=self._settings.retry_exchange,
                headers=headers,
            )
            await message.ack()
            messages_consumed_total.labels(queue=self._queue_name, result="retry").inc()
            logger.warning(
                "The message failed and was scheduled for a delayed retry.",
                extra={
                    "queue": self._queue_name,
                    "message_id": envelope.message_id,
                    "attempt": next_attempt,
                    "retry_delay_ms": self._settings.retry_delay_ms,
                },
            )
        except Exception:
            messages_consumed_total.labels(queue=self._queue_name, result="nack").inc()
            logger.exception(
                "Failed to schedule a retry; dead-lettering the message instead.",
                extra={"queue": self._queue_name, "message_id": envelope.message_id},
            )
            await message.nack(requeue=False)
