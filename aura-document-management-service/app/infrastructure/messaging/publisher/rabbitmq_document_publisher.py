import json
import logging
import pika
from pika.adapters.blocking_connection import BlockingChannel, BlockingConnection

from app.application.exceptions.exceptions import MessagingError
from app.configuration.environment_variables import environment_variables
from app.infrastructure.messaging.publisher.interfaces.document_publisher_interface import DocumentPublisherInterface


logger = logging.getLogger(__name__)


class RabbitMQDocumentPublisher(DocumentPublisherInterface):
    def __init__(self) -> None:
        try:
            credentials = pika.PlainCredentials(
                environment_variables.rabbitmq_user,
                environment_variables.rabbitmq_password,
            )

            parameters = pika.ConnectionParameters(
                host=environment_variables.rabbitmq_host,
                port=environment_variables.rabbitmq_port,
                credentials=credentials,
            )

            self.connection: BlockingConnection = pika.BlockingConnection(parameters)
            self.channel: BlockingChannel = self.connection.channel()

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

            logger.info("RabbitMQ publisher initialized successfully")

        except Exception as e:
            logger.exception("Failed to initialize RabbitMQ connection")
            raise MessagingError("Failed to initialize RabbitMQ connection") from e

    def publish_document(self,
                         document_id: int) -> None:
        try:
            message = json.dumps({"document_id": document_id})

            self.channel.basic_publish(
                exchange=environment_variables.exchange,
                routing_key=environment_variables.queue,
                body=message,
                properties=pika.BasicProperties(delivery_mode=2),
            )

            logger.info("Published document message to RabbitMQ", extra={"document_id": document_id})

        except Exception as e:
            logger.exception("Failed to publish document message to RabbitMQ")
            raise MessagingError("Failed to publish message to queue") from e

    def close(self) -> None:
        try:
            if self.connection and not self.connection.is_closed:
                self.connection.close()
                logger.info("RabbitMQ connection closed")
        except Exception as e:
            logger.warning("Error closing RabbitMQ connection", exc_info=e)