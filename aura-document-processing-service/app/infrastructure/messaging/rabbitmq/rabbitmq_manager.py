import asyncio
import logging
import time
from typing import Any, Awaitable, Callable, Dict, Optional
import aio_pika
import aio_pika.abc
from fastapi import HTTPException, Request, status
from tenacity import before_sleep_log, retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.infrastructure.messaging.rabbitmq.exceptions.rabbitmq_manager_exception import (
    RabbitMQConnectionException,
    RabbitMQNotStartedException,
    RabbitMQPublishException,
    RabbitMQTopologyException,
)
from app.infrastructure.messaging.rabbitmq.interfaces.rabbitmq_manager_interface import RabbitMQManagerInterface
from app.infrastructure.messaging.rabbitmq.rabbitmq_manager_settings import RabbitMQManagerSettings

logger = logging.getLogger(__name__)


class RabbitMQManager(RabbitMQManagerInterface):
    def __init__(self, rabbit_mq_manager_settings: Optional[RabbitMQManagerSettings] = None) -> None:
        self._settings = rabbit_mq_manager_settings or RabbitMQManagerSettings()
        self._connection: Optional[aio_pika.abc.AbstractRobustConnection] = None
        self._channel: Optional[aio_pika.abc.AbstractChannel] = None
        self._exchanges: Dict[str, aio_pika.abc.AbstractExchange] = {}
        self._consumer_task: Optional[asyncio.Task] = None

        self._lifecycle_lock = asyncio.Lock()
        self._is_started: bool = False

    async def start(self) -> None:
        async with self._lifecycle_lock:
            if self._is_started:
                logger.debug("RabbitMQManager already started — skipping")
                return

            logger.info("Starting RabbitMQManager", extra={"url": self._settings.url_safe})

            try:
                self._connection = await aio_pika.connect_robust(
                    self._settings.url.get_secret_value(),
                    timeout=self._settings.tcp_connect_timeout_seconds,
                )
                self._channel = await self._connection.channel()
                await self._channel.set_qos(prefetch_count=self._settings.prefetch_count)
                await self._declare_topology()
                self._is_started = True
                logger.info("RabbitMQManager started successfully")

            except Exception as e:
                await self._cleanup_resources()
                logger.exception("Failed to start RabbitMQManager")
                raise RabbitMQConnectionException(f"Failed to connect to RabbitMQ: {e}") from e

    async def stop(self) -> None:
        async with self._lifecycle_lock:
            if not self._is_started:
                logger.debug("RabbitMQManager already stopped — skipping")
                return

            logger.info("Stopping RabbitMQManager")

            if self._consumer_task and not self._consumer_task.done():
                self._consumer_task.cancel()
                try:
                    await self._consumer_task
                except asyncio.CancelledError:
                    pass
                self._consumer_task = None

            await self._cleanup_resources()
            self._is_started = False
            logger.info("RabbitMQManager stopped successfully")

    @property
    def is_started(self) -> bool:
        return self._is_started

    @property
    def settings(self) -> RabbitMQManagerSettings:
        return self._settings

    async def publish(
            self,
            routing_key: str,
            body: bytes,
            exchange_name: Optional[str] = None,
            persistent: bool = True,
            headers: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._assert_started()

        target_exchange = exchange_name or self._settings.exchange

        @retry(
            stop=stop_after_attempt(self._settings.retry_max_attempts),
            wait=wait_exponential(
                min=self._settings.retry_backoff_min_seconds,
                max=self._settings.retry_backoff_max_seconds,
            ),
            retry=retry_if_exception_type(Exception),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            reraise=True,
        )
        async def _publish_attempt() -> None:
            channel = await self._connection.channel()
            try:
                exchange = await channel.get_exchange(target_exchange)
                message = aio_pika.Message(
                    body=body,
                    delivery_mode=(
                        aio_pika.DeliveryMode.PERSISTENT
                        if persistent
                        else aio_pika.DeliveryMode.NOT_PERSISTENT
                    ),
                    headers=headers or {},
                )
                await exchange.publish(message, routing_key=routing_key)
            finally:
                await channel.close()

        try:
            await _publish_attempt()
            logger.debug(
                "Message published",
                extra={"exchange": target_exchange, "routing_key": routing_key, "size_bytes": len(body)},
            )
        except Exception as e:
            logger.error(
                "Failed to publish message",
                extra={"exchange": target_exchange, "routing_key": routing_key},
            )
            raise RabbitMQPublishException(
                f"Failed to publish to '{target_exchange}/{routing_key}': {e}"
            ) from e

    async def start_consumer(
            self,
            queue_name: str,
            callback: Callable[[aio_pika.abc.AbstractIncomingMessage], Awaitable[None]],
            prefetch_count: Optional[int] = None,
    ) -> None:
        self._assert_started()

        effective_prefetch = prefetch_count or self._settings.prefetch_count

        async def _consume_loop() -> None:
            logger.info(
                "Starting RabbitMQ consumer",
                extra={"queue": queue_name, "prefetch_count": effective_prefetch},
            )
            while True:
                try:
                    channel = await self._connection.channel()
                    await channel.set_qos(prefetch_count=effective_prefetch)
                    queue = await channel.get_queue(queue_name)

                    async with queue.iterator() as queue_iter:
                        async for message in queue_iter:
                            await callback(message)

                except asyncio.CancelledError:
                    logger.info("Consumer task cancelled", extra={"queue": queue_name})
                    break

                except Exception as exc:
                    logger.warning(
                        "Consumer channel lost — reconnecting",
                        extra={
                            "queue": queue_name,
                            "error": str(exc),
                            "delay_seconds": self._settings.consumer_reconnect_delay_seconds,
                        },
                    )
                    await asyncio.sleep(self._settings.consumer_reconnect_delay_seconds)

        self._consumer_task = asyncio.create_task(
            _consume_loop(), name=f"rabbitmq-consumer-{queue_name}"
        )
        logger.info("Consumer task created", extra={"queue": queue_name})

    async def health_check(self) -> Dict[str, Any]:
        if not self._is_started or not self._connection:
            return {"status": "unhealthy", "started": False, "error": "Connection not started"}

        try:
            start_time = time.monotonic()
            channel = await self._connection.channel()
            await channel.close()
            latency_ms = round((time.monotonic() - start_time) * 1000, 2)

            return {
                "status": "healthy",
                "started": True,
                "latency_ms": latency_ms,
                "url": self._settings.url_safe,
            }
        except Exception as exc:
            logger.warning("RabbitMQ health check failed", extra={"error": str(exc)})
            return {"status": "unhealthy", "started": True, "error": "Health probe failed"}

    async def __aenter__(self) -> "RabbitMQManager":
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.stop()

    def _assert_started(self) -> None:
        if not self._is_started or not self._connection:
            raise RabbitMQNotStartedException(
                "RabbitMQManager is not started. Call start() first."
            )

    async def _declare_topology(self) -> None:
        assert self._channel is not None

        try:
            dlx_exchange = await self._channel.declare_exchange(
                self._settings.dlx_exchange,
                aio_pika.ExchangeType.DIRECT,
                durable=True,
            )
            dlq = await self._channel.declare_queue(self._settings.dlq_queue, durable=True)
            await dlq.bind(dlx_exchange, routing_key=self._settings.dlq_queue)

            exchange = await self._channel.declare_exchange(
                self._settings.exchange,
                aio_pika.ExchangeType.DIRECT,
                durable=True,
            )

            queue_args: Dict[str, Any] = {
                "x-dead-letter-exchange": self._settings.dlx_exchange,
                "x-dead-letter-routing-key": self._settings.dlq_queue,
            }
            if self._settings.message_ttl_ms is not None:
                queue_args["x-message-ttl"] = self._settings.message_ttl_ms

            document_ingestion_queue = await self._channel.declare_queue(
                self._settings.document_ingestion_queue,
                durable=True,
                arguments=queue_args,
            )
            await document_ingestion_queue.bind(exchange, routing_key=self._settings.document_ingestion_queue)

            self._exchanges[self._settings.exchange] = exchange
            self._exchanges[self._settings.dlx_exchange] = dlx_exchange

            logger.info(
                "RabbitMQ topology declared",
                extra={
                    "exchange": self._settings.exchange,
                    "document_ingestion_queue": self._settings.document_ingestion_queue,
                    "dlx_exchange": self._settings.dlx_exchange,
                    "dlq_queue": self._settings.dlq_queue,
                },
            )
        except Exception as e:
            raise RabbitMQTopologyException(f"Failed to declare RabbitMQ topology: {e}") from e

    async def _cleanup_resources(self) -> None:
        self._exchanges.clear()

        if self._channel and not self._channel.is_closed:
            try:
                await self._channel.close()
            except Exception:
                pass
        self._channel = None

        if self._connection and not self._connection.is_closed:
            try:
                await self._connection.close()
            except Exception:
                pass
        self._connection = None


async def get_rabbitmq_manager(request: Request) -> RabbitMQManagerInterface:
    try:
        manager: RabbitMQManagerInterface = request.app.state.rabbitmq_manager
        if not manager.is_started:
            logger.error("RabbitMQManager found in app state but not started")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Messaging (RabbitMQ) is not available",
            )
        return manager
    except AttributeError:
        logger.error("RabbitMQManager not found in application state")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Messaging service is not configured",
        )
