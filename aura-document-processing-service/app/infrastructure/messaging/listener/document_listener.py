import json
import logging
from typing import Callable, Optional
import threading

from app.application.exceptions.exceptions import MessagingError
from app.configuration.environment_variables import environment_variables
from app.infrastructure.messaging.rabbitmq_client import RabbitmqClient


logger = logging.getLogger(__name__)


class DocumentListener:
    def __init__(self, rabbitmq_client: RabbitmqClient):
        self.rabbitmq_client = rabbitmq_client
        self.queue = environment_variables.queue
        self.exchange = environment_variables.exchange
        self._consuming = False
        self._consumer_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def start_consuming(
            self,
            callback: Callable[[dict], None],
            prefetch_count: int = 1
    ) -> None:
        try:
            if self._consuming:
                logger.warning("Consumer already running")
                return

            self.rabbitmq_client._ensure_connection()

            self.rabbitmq_client.channel.basic_qos(prefetch_count=prefetch_count)

            def wrapped_callback(ch, method, properties, body):
                try:
                    message = json.loads(body)

                    logger.info(
                        "Message received from RabbitMQ",
                        extra={
                            "queue": self.queue,
                            "delivery_tag": method.delivery_tag,
                            "msg_body": message
                        }
                    )

                    callback(message)

                    ch.basic_ack(delivery_tag=method.delivery_tag)

                    logger.info(
                        "Message processed successfully",
                        extra={
                            "delivery_tag": method.delivery_tag,
                            "msg_body": message
                        }
                    )

                except json.JSONDecodeError as e:
                    logger.exception("Failed to parse message JSON")
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

                except Exception as e:
                    logger.exception("Error processing message")
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

            self.rabbitmq_client.channel.basic_consume(
                queue=self.queue,
                on_message_callback=wrapped_callback,
                auto_ack=False
            )

            self._consuming = True

            logger.info(
                "Started consuming messages from RabbitMQ",
                extra={
                    "queue": self.queue,
                    "prefetch_count": prefetch_count
                }
            )

            self.rabbitmq_client.channel.start_consuming()

        except KeyboardInterrupt:
            logger.info("Consumer interrupted by user")
            self.stop_consuming()

        except Exception as e:
            self._consuming = False
            logger.exception("Error while consuming messages")
            raise MessagingError("Error while consuming messages") from e

    def start_consuming_background(
            self,
            callback: Callable[[dict], None],
            prefetch_count: int = 1
    ) -> None:
        if self._consuming:
            logger.warning("Consumer already running")
            return

        self._stop_event.clear()

        def consume_in_thread():
            try:
                self.start_consuming(callback, prefetch_count)
            except Exception as e:
                logger.exception("Error in consumer thread")

        self._consumer_thread = threading.Thread(
            target=consume_in_thread,
            daemon=True,
            name="RabbitMQ-Consumer"
        )
        self._consumer_thread.start()

        logger.info("Consumer thread started")

    def stop_consuming(self) -> None:
        if not self._consuming:
            logger.warning("Consumer not running")
            return

        try:
            logger.info("Stopping consumer...")

            self._stop_event.set()

            if self.rabbitmq_client.channel and not self.rabbitmq_client.channel.is_closed:
                self.rabbitmq_client.channel.stop_consuming()

            if self._consumer_thread and self._consumer_thread.is_alive():
                self._consumer_thread.join(timeout=5)

            self._consuming = False

            logger.info("Consumer stopped successfully")

        except Exception as e:
            logger.exception("Error stopping consumer")
            self._consuming = False

    def is_consuming(self) -> bool:
        return self._consuming