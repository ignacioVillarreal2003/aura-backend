import json
import logging
import threading
from typing import Optional
import pika
from pika.adapters.blocking_connection import BlockingChannel, BlockingConnection


from app.application.exceptions.exceptions import MessagingError
from app.configuration.environment_variables import environment_variables


logger = logging.getLogger(__name__)


class RabbitmqClient:
    _instance: Optional['RabbitmqClient'] = None
    _lock: threading.Lock = threading.Lock()
    _initialized: bool = False

    def __new__(cls) -> 'RabbitmqClient':
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return

        with self._lock:
            if self._initialized:
                return

            self.connection: Optional[BlockingConnection] = None
            self.channel: Optional[BlockingChannel] = None
            self._connection_lock = threading.Lock()
            self._connect()
            self._initialized = True

    def _connect(self) -> None:
        try:
            credentials = pika.PlainCredentials(
                environment_variables.rabbitmq_user,
                environment_variables.rabbitmq_password,
            )

            parameters = pika.ConnectionParameters(
                host=environment_variables.rabbitmq_host,
                port=environment_variables.rabbitmq_port,
                credentials=credentials,
                heartbeat=600,
                blocked_connection_timeout=300,
            )

            self.connection = pika.BlockingConnection(parameters)
            self.channel = self.connection.channel()

            self.channel.exchange_declare(
                exchange=environment_variables.exchange,
                exchange_type="direct",
                durable=True,
            )

            self.channel.queue_declare(
                queue=environment_variables.queue,
                durable=True,
            )

            self.channel.queue_bind(
                exchange=environment_variables.exchange,
                queue=environment_variables.queue,
                routing_key=environment_variables.queue,
            )

            logger.info("RabbitMQ client initialized successfully")

        except Exception as e:
            logger.exception("Failed to initialize RabbitMQ connection")
            raise MessagingError("Failed to initialize RabbitMQ connection") from e

    def _ensure_connection(self) -> None:
        with self._connection_lock:
            if (self.connection is None or self.connection.is_closed or
                    self.channel is None or self.channel.is_closed):
                logger.warning("RabbitMQ connection closed — reconnecting...")
                self._reconnect()

    def _reconnect(self) -> None:
        try:
            self._close_connection()

            self._connect()

            logger.info("Reconnected to RabbitMQ successfully")
        except Exception as e:
            logger.exception("Failed to reconnect to RabbitMQ")
            raise MessagingError("Failed to reconnect to RabbitMQ") from e

    def publish(self,
                message: dict,
                routing_key: str,
                exchange: str) -> None:
        try:
            self._ensure_connection()

            message_body = json.dumps(message)

            self.channel.basic_publish(
                exchange=exchange,
                routing_key=routing_key,
                body=message_body,
                properties=pika.BasicProperties(
                    delivery_mode=2,
                    content_type="application/json",
                ),
            )

            logger.info(
                "Published message to RabbitMQ",
                extra={
                    "exchange": exchange,
                    "routing_key": routing_key,
                    "message_body": message,
                }
            )

        except Exception as e:
            logger.exception("Failed to publish message to RabbitMQ")
            raise MessagingError("Failed to publish message to queue") from e

    def _close_connection(self) -> None:
        try:
            if self.channel and not self.channel.is_closed:
                self.channel.close()
            if self.connection and not self.connection.is_closed:
                self.connection.close()
        except Exception as e:
            logger.warning("Error closing RabbitMQ connection", exc_info=e)

    def close(self) -> None:
        with self._connection_lock:
            self._close_connection()
            logger.info("RabbitMQ connection closed")