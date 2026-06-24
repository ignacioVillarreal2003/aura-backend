import asyncio
import logging
import time
from typing import Any, Awaitable, Callable, Optional
import aio_pika
import aio_pika.abc
from aio_pika.exceptions import (
    AMQPConnectionError,
    ChannelClosed,
    ChannelInvalidStateError,
    ConnectionClosed,
)
from fastapi import HTTPException, Request, status
from tenacity import before_sleep_log, retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.infrastructure.messaging.rabbitmq.exceptions.rabbitmq_manager_exception import (
    RabbitMQConnectionException,
    RabbitMQNotStartedException,
    RabbitMQPublishException,
    RabbitMQTopologyException
)
from app.infrastructure.messaging.rabbitmq.interfaces.rabbitmq_manager_interface import RabbitMQManagerInterface
from app.infrastructure.messaging.rabbitmq.rabbitmq_manager_settings import RabbitMQManagerSettings

logger = logging.getLogger(__name__)

_PUBLISH_RETRY_EXCEPTIONS: tuple[type[BaseException], ...] = (
    AMQPConnectionError,
    ConnectionClosed,
    ChannelClosed,
    ChannelInvalidStateError,
    asyncio.TimeoutError,
    ConnectionResetError,
    BrokenPipeError,
    OSError,
)


class RabbitMQManager(RabbitMQManagerInterface):
    def __init__(
            self,
            rabbit_mq_manager_settings: Optional[RabbitMQManagerSettings] = None
    ) -> None:
        self._settings = rabbit_mq_manager_settings or RabbitMQManagerSettings()
        self._connection: Optional[aio_pika.abc.AbstractRobustConnection] = None
        self._channel: Optional[aio_pika.abc.AbstractChannel] = None
        self._publish_channel: Optional[aio_pika.abc.AbstractChannel] = None
        self._publish_lock = asyncio.Lock()
        self._exchanges: dict[str, aio_pika.abc.AbstractExchange] = {}
        self._consumer_tasks: list[asyncio.Task] = []
        self._publish_with_retry: Optional[Any] = None

        self._lifecycle_lock = asyncio.Lock()
        self._is_started: bool = False

    def _connect_robust_kwargs(
            self
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "heartbeat": self._settings.heartbeat_seconds,
            "client_properties": {
                "connection_name": self._settings.client_connection_name,
            },
        }
        if self._settings.blocked_connection_timeout_seconds is not None:
            kwargs["blocked_connection_timeout"] = self._settings.blocked_connection_timeout_seconds
        return kwargs

    async def start(
            self
    ) -> None:
        async with self._lifecycle_lock:
            if self._is_started:
                logger.debug("The RabbitMQ manager is already running; skipping start.")
                return

            logger.info(
                "Starting the RabbitMQ connection and topology.",
                extra={
                    "broker_url": self._settings.url_safe
                }
            )

            try:
                self._connection = await aio_pika.connect_robust(
                    self._settings.url.get_secret_value(),
                    timeout=self._settings.tcp_connect_timeout_seconds,
                    **self._connect_robust_kwargs(),
                )
                self._channel = await self._connection.channel()
                await self._channel.set_qos(prefetch_count=self._settings.prefetch_count)
                await self._declare_topology()
                self._publish_channel = await self._connection.channel()
                self._publish_with_retry = retry(
                    stop=stop_after_attempt(self._settings.retry_max_attempts),
                    wait=wait_exponential(
                        min=self._settings.retry_backoff_min_seconds,
                        max=self._settings.retry_backoff_max_seconds,
                    ),
                    retry=retry_if_exception_type(_PUBLISH_RETRY_EXCEPTIONS),
                    before_sleep=before_sleep_log(logger, logging.WARNING),
                    reraise=True,
                )(self._publish_attempt_core)
                self._is_started = True
                logger.info("The RabbitMQ manager started successfully.")

            except Exception as e:
                await self._cleanup_resources()
                logger.exception("The RabbitMQ manager failed to start.")
                raise RabbitMQConnectionException("Could not connect to RabbitMQ.") from e

    async def stop(
            self
    ) -> None:
        async with self._lifecycle_lock:
            if not self._is_started:
                logger.debug("The RabbitMQ manager is already stopped; nothing to do.")
                return

            logger.info("Stopping the RabbitMQ manager.")

            for task in list(self._consumer_tasks):
                if task and not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
            self._consumer_tasks.clear()

            await self._cleanup_resources()
            self._is_started = False
            logger.info("The RabbitMQ manager stopped successfully.")

    @property
    def is_started(
            self
    ) -> bool:
        return self._is_started

    @property
    def settings(
            self
    ) -> RabbitMQManagerSettings:
        return self._settings

    async def publish(
            self,
            routing_key: str,
            body: bytes,
            exchange_name: Optional[str] = None,
            persistent: bool = True,
            headers: Optional[dict[str, Any]] = None
    ) -> None:
        self._assert_started()
        assert self._publish_with_retry is not None

        target_exchange = exchange_name or self._settings.exchange

        try:
            await self._publish_with_retry(target_exchange, routing_key, body, persistent, headers)
            logger.debug(
                "A message was published to the broker.",
                extra={
                    "exchange": target_exchange,
                    "routing_key": routing_key,
                    "size_bytes": len(body)
                }
            )
        except Exception as e:
            logger.error(
                "Publishing a message to the broker failed after retries.",
                extra={
                    "exchange": target_exchange,
                    "routing_key": routing_key
                }
            )
            raise RabbitMQPublishException("Failed to publish the message to RabbitMQ.") from e

    async def _publish_attempt_core(
            self,
            target_exchange: str,
            routing_key: str,
            body: bytes,
            persistent: bool,
            headers: Optional[dict[str, Any]],
    ) -> None:
        assert self._connection is not None
        async with self._publish_lock:
            if self._publish_channel is None or self._publish_channel.is_closed:
                self._publish_channel = await self._connection.channel()
            exchange = await self._publish_channel.get_exchange(target_exchange)
            message = aio_pika.Message(
                body=body,
                delivery_mode=(
                    aio_pika.DeliveryMode.PERSISTENT
                    if persistent
                    else aio_pika.DeliveryMode.NOT_PERSISTENT
                ),
                headers=headers or {}
            )
            await asyncio.wait_for(
                exchange.publish(message, routing_key=routing_key),
                timeout=self._settings.publish_timeout_seconds,
            )

    async def start_consumer(
            self,
            queue_name: str,
            callback: Callable[[aio_pika.abc.AbstractIncomingMessage], Awaitable[None]],
            prefetch_count: Optional[int] = None
    ) -> None:
        self._assert_started()

        effective_prefetch = prefetch_count or self._settings.prefetch_count

        async def _consume_loop() -> None:
            logger.info(
                "Starting the background consumer for the queue.",
                extra={
                    "queue": queue_name,
                    "prefetch_count": effective_prefetch
                }
            )
            while True:
                try:
                    connection = self._connection
                    if connection is None or connection.is_closed:
                        raise ConnectionClosed("Connection is not available.")
                    channel = await connection.channel()
                    await channel.set_qos(prefetch_count=effective_prefetch)
                    queue = await channel.get_queue(queue_name)

                    async with queue.iterator() as queue_iter:
                        async for message in queue_iter:
                            await callback(message)

                except asyncio.CancelledError:
                    logger.info(
                        "The consumer task was cancelled.",
                        extra={
                            "queue": queue_name
                        }
                    )
                    break

                except Exception:
                    logger.warning(
                        "The consumer channel was lost; reconnecting after a short delay.",
                        extra={
                            "queue": queue_name,
                            "reason": "channel_lost",
                            "delay_seconds": self._settings.consumer_reconnect_delay_seconds
                        }
                    )
                    await asyncio.sleep(self._settings.consumer_reconnect_delay_seconds)

        task = asyncio.create_task(
            _consume_loop(), name=f"rabbitmq-consumer-{queue_name}"
        )
        self._consumer_tasks.append(task)
        logger.info(
            "The consumer background task was created.",
            extra={
                "queue": queue_name
            }
        )

    async def health_check(
            self
    ) -> dict[str, Any]:
        if not self._is_started or not self._connection:
            return {
                "status": "unhealthy",
                "started": False,
                "error": "Connection not started"
            }

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
                "topology_declared": True,
            }
        except Exception:
            logger.warning("The RabbitMQ health check failed.")
            return {
                "status": "unhealthy",
                "started": True,
                "error": "Health probe failed"
            }

    async def __aenter__(
            self
    ) -> "RabbitMQManager":
        await self.start()
        return self

    async def __aexit__(
            self,
            exc_type,
            exc_val,
            exc_tb
    ) -> None:
        await self.stop()

    def _assert_started(
            self
    ) -> None:
        if not self._is_started or not self._connection:
            raise RabbitMQNotStartedException("The RabbitMQ manager is not started; call start() first.", )

    async def _declare_work_queue(
            self,
            exchange: aio_pika.abc.AbstractExchange,
            queue_name: str,
            queue_args: dict[str, Any],
    ) -> None:
        queue = await self._channel.declare_queue(
            queue_name,
            durable=True,
            arguments=queue_args
        )
        await queue.bind(exchange, routing_key=queue_name)

    async def _declare_topology(
            self
    ) -> None:
        assert self._channel is not None

        try:
            dlx_exchange = await self._channel.declare_exchange(
                self._settings.dlx_exchange,
                aio_pika.ExchangeType.DIRECT,
                durable=True
            )
            dlq = await self._channel.declare_queue(self._settings.dlq_queue, durable=True)
            await dlq.bind(dlx_exchange, routing_key=self._settings.dlq_queue)

            exchange = await self._channel.declare_exchange(
                self._settings.exchange,
                aio_pika.ExchangeType.DIRECT,
                durable=True
            )

            queue_args: dict[str, Any] = {
                "x-dead-letter-exchange": self._settings.dlx_exchange,
                "x-dead-letter-routing-key": self._settings.dlq_queue
            }
            if self._settings.message_ttl_ms is not None:
                queue_args["x-message-ttl"] = self._settings.message_ttl_ms

            await self._declare_work_queue(exchange, self._settings.document_ingestion_queue, queue_args)
            await self._declare_work_queue(exchange, self._settings.graph_extraction_queue, queue_args)
            await self._declare_work_queue(exchange, self._settings.document_enrichment_queue, queue_args)
            await self._declare_work_queue(exchange, self._settings.document_reembed_queue, queue_args)
            await self._declare_work_queue(exchange, self._settings.document_reprocess_queue, queue_args)
            await self._declare_work_queue(exchange, self._settings.document_purge_queue, queue_args)

            self._exchanges[self._settings.exchange] = exchange
            self._exchanges[self._settings.dlx_exchange] = dlx_exchange

            logger.info(
                "The RabbitMQ topology was declared successfully.",
                extra={
                    "exchange": self._settings.exchange,
                    "document_ingestion_queue": self._settings.document_ingestion_queue,
                    "graph_extraction_queue": self._settings.graph_extraction_queue,
                    "document_enrichment_queue": self._settings.document_enrichment_queue,
                    "dlx_exchange": self._settings.dlx_exchange,
                    "dlq_queue": self._settings.dlq_queue
                }
            )
        except Exception as e:
            raise RabbitMQTopologyException("Failed to declare the RabbitMQ exchanges and queues.") from e

    async def _cleanup_resources(
            self
    ) -> None:
        self._exchanges.clear()
        self._publish_with_retry = None

        if self._publish_channel and not self._publish_channel.is_closed:
            try:
                await self._publish_channel.close()
            except Exception:
                pass
        self._publish_channel = None

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


async def get_rabbitmq_manager(
        request: Request
) -> RabbitMQManagerInterface:
    manager = getattr(request.app.state, "rabbitmq_manager", None)
    if manager is None:
        logger.error("The RabbitMQ manager was not registered on the application state.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Messaging service is not configured"
        )
    if not manager.is_started:
        logger.error("The RabbitMQ manager exists on the application but has not been started.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Messaging (RabbitMQ) is not available"
        )
    return manager
