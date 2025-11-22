import json
import logging
import threading
import asyncio

from app.application.exceptions.api_exceptions import MessagingError
from app.application.services.interfaces.question_service_interface import QuestionServiceInterface
from app.configuration.environment_variables import environment_variables
from app.domain.dtos.question_request import QuestionRequest
from app.infrastructure.messaging.interfaces.question_listener_interface import QuestionListenerInterface
from app.infrastructure.messaging.rabbitmq_client import RabbitmqClient

logger = logging.getLogger(__name__)


class QuestionListener(QuestionListenerInterface):
    def __init__(self,
                 rabbitmq_client: RabbitmqClient,
                 question_service: QuestionServiceInterface):
        self.rabbitmq_client = rabbitmq_client
        self.question_service = question_service

        self.queue = environment_variables.question_queue
        self.exchange = environment_variables.exchange

        self._consuming = False
        self._consumer_thread = None
        self._stop_event = threading.Event()

    def _handle_message_sync(self, message_dict: dict):
        try:
            request = QuestionRequest(**message_dict)

            logger.info("Processing QuestionRequest", extra={"request": request.model_dump()})

            result = asyncio.run(self.question_service.generate_response(request))

            logger.info("LLM answer generated successfully",
                        extra={"answer": result.answer})

        except Exception:
            logger.exception("Error processing QuestionRequest")

    def start_consuming(self,
                        prefetch_count: int = 1) -> None:
        try:
            if self._consuming:
                logger.warning("Consumer already running")
                return

            self.rabbitmq_client._ensure_connection()

            self.rabbitmq_client.channel.basic_qos(prefetch_count=prefetch_count)

            def wrapped_callback(ch, method, properties, body):
                try:
                    message = json.loads(body)

                    logger.info("Message received", extra={
                        "queue": self.queue,
                        "delivery_tag": method.delivery_tag
                    })

                    self._handle_message_sync(message)

                    ch.basic_ack(delivery_tag=method.delivery_tag)

                except json.JSONDecodeError:
                    logger.exception("Invalid JSON received")
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

                except Exception:
                    logger.exception("Unhandled error processing message")
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

            self.rabbitmq_client.channel.basic_consume(
                queue=self.queue,
                on_message_callback=wrapped_callback,
                auto_ack=False
            )

            self._consuming = True

            logger.info("Started consuming", extra={
                "queue": self.queue,
                "prefetch": prefetch_count
            })

            self.rabbitmq_client.channel.start_consuming()

        except KeyboardInterrupt:
            self.stop_consuming()

        except Exception as e:
            self._consuming = False
            logger.exception("Error while consuming messages")
            raise MessagingError("Error while consuming messages") from e

    def start_consuming_background(self, prefetch_count: int = 1) -> None:
        if self._consuming:
            logger.warning("Consumer already running")
            return

        self._stop_event.clear()

        def consume():
            try:
                self.start_consuming(prefetch_count)
            except Exception:
                logger.exception("Error in consumer thread")

        self._consumer_thread = threading.Thread(
            target=consume,
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

            logger.info("Consumer stopped")

        except Exception:
            logger.exception("Error stopping consumer")
            self._consuming = False
