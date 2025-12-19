import json
import logging
import asyncio
from typing import Optional
from aio_pika import connect_robust, Message, ExchangeType
from aio_pika.robust_connection import RobustConnection
from aio_pika.robust_channel import RobustChannel
from aio_pika.robust_exchange import RobustExchange

from app.application.exceptions.app_exceptions import RabbitMQError
from app.configuration.environment_variables import environment_variables

logger = logging.getLogger(__name__)


class RabbitmqClient:
    _instance: Optional["RabbitmqClient"] = None
    _lock: asyncio.Lock = asyncio.Lock()

    def __init__(self) -> None:
        self.connection: Optional[RobustConnection] = None
        self.channel: Optional[RobustChannel] = None
        self.exchange: Optional[RobustExchange] = None

    def __new__(cls) -> "RabbitmqClient":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    async def get_instance(cls) -> "RabbitmqClient":
        if cls._instance is None:
            async with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    async def connect(self) -> None:
        async with self._lock:
            try:
                if self.connection and not self.connection.is_closed:
                    return

                self.connection = await connect_robust(
                    host=environment_variables.rabbitmq_host,
                    port=environment_variables.rabbitmq_port,
                    login=environment_variables.rabbitmq_user,
                    password=environment_variables.rabbitmq_password,
                    heartbeat=600,
                )

                self.channel = await self.connection.channel()

                self.exchange = await self.channel.declare_exchange(
                    name=environment_variables.exchange,
                    type=ExchangeType.DIRECT,
                    durable=True,
                )

                logger.info("RabbitMQ broker connection established")

            except Exception as e:
                logger.exception("RabbitMQ connection initialization failed")
                raise RabbitMQError("RabbitMQ connection initialization failed") from e

    async def get_channel(self) -> RobustChannel:
        if not self.channel or self.channel.is_closed:
            await self.connect()
        return self.channel

    async def publish(self,
                      message: dict,
                      routing_key: Optional[str] = None) -> None:
        try:
            await self.connect()

            if not self.exchange:
                logger.error("RabbitMQ exchange unavailable")
                raise RabbitMQError("RabbitMQ exchange unavailable")

            body: bytes = json.dumps(message).encode()
            key: str = routing_key or environment_variables.question_queue

            await self.exchange.publish(
                Message(
                    body=body,
                    delivery_mode=2,
                    content_type="application/json"
                ),
                routing_key=key
            )

            logger.info("RabbitMQ message published to broker",)

        except Exception as e:
            logger.exception("RabbitMQ message publish failed")
            raise RabbitMQError("RabbitMQ message publish failed") from e

    async def close(self) -> None:
        try:
            if not self.connection or self.connection.is_closed:
                return

            await self.connection.close()
            self.channel = None
            self.exchange = None

            logger.info("RabbitMQ broker connection terminated")

        except Exception as e:
            logger.exception("RabbitMQ shutdown process failed")
            raise RabbitMQError("RabbitMQ shutdown process failed") from e
