import pika
import json
import logging

from app.application.services.ingestion_service import IngestionService
from app.configuration.db_session import get_db_session, get_sync_db
from app.configuration.environment_variables import environment_variables

logger = logging.getLogger(__name__)


class RabbitMQConsumer:
    def __init__(self):
        self._connection = None
        self._channel = None
        self._connect()

    def _connect(self):
        credentials = pika.PlainCredentials(
            environment_variables.rabbitmq_user,
            environment_variables.rabbitmq_password
        )

        parameters = pika.ConnectionParameters(
            host=environment_variables.rabbitmq_host,
            port=environment_variables.rabbitmq_port,
            credentials=credentials,
            heartbeat=600,
            blocked_connection_timeout=300
        )

        self._connection = pika.BlockingConnection(parameters)
        self._channel = self._connection.channel()

        self._channel.exchange_declare(
            exchange=environment_variables.exchange,
            exchange_type="direct",
            durable=True
        )

        self._channel.queue_declare(
            queue=environment_variables.queue,
            durable=True
        )

        self._channel.queue_bind(
            exchange=environment_variables.exchange,
            queue=environment_variables.queue,
            routing_key=environment_variables.queue
        )

        logger.info(f"Connected to RabbitMQ at {environment_variables.rabbitmq_host}")

    def _callback(self, ch, method, properties, body):
        try:
            message = json.loads(body)
            document_id = message.get("document_id")

            logger.info(f"Received document_id={document_id}")

            with get_sync_db() as db:
                service = IngestionService(db)
                service.process_document(document_id)

            ch.basic_ack(delivery_tag=method.delivery_tag)
            logger.info(f"✅ Document {document_id} processed successfully")

        except Exception as e:
            logger.exception(f"Error processing message: {e}")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

    def start_consuming(self):
        self._channel.basic_consume(
            queue=environment_variables.queue,
            on_message_callback=self._callback,
            auto_ack=False
        )
        logger.info(f"Waiting for messages in '{environment_variables.queue}'...")
        self._channel.start_consuming()

    def close(self):
        if self._connection and not self._connection.is_closed:
            self._connection.close()
            logger.info("RabbitMQ connection closed.")