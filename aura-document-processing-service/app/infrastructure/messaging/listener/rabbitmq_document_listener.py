import json
import logging
import pika
from pika.adapters.blocking_connection import BlockingChannel, BlockingConnection

from app.application.services.ingestion_service import IngestionService
from app.application.services.minio_storage_service import MinioStorageService
from app.configuration.environment_variables import environment_variables
from app.configuration.database_session_manager import DatabaseSessionManager
from app.application.exceptions.exceptions import MessagingError
from app.infrastructure.messaging.listener.interfaces.document_listener_interface import DocumentListenerInterface
from app.infrastructure.persistence.repositories.document_repository import DocumentRepository
from app.infrastructure.persistence.repositories.fragment_repository import FragmentRepository


logger = logging.getLogger(__name__)


class RabbitMQDocumentListener(DocumentListenerInterface):
    def __init__(self,
                 db_session_manager: DatabaseSessionManager) -> None:
        self.db_session_manager = db_session_manager

        try:
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

            self.connection: BlockingConnection = pika.BlockingConnection(parameters)
            self.channel: BlockingChannel = self.connection.channel()

            self.channel.exchange_declare(
                exchange=environment_variables.exchange,
                exchange_type="direct",
                durable=True
            )

            self.channel.queue_declare(
                queue=environment_variables.queue,
                durable=True
            )

            self.channel.queue_bind(
                exchange=environment_variables.exchange,
                queue=environment_variables.queue,
                routing_key=environment_variables.queue
            )

            logger.info("RabbitMQ listener initialized successfully")

        except Exception as e:
            logger.exception("Failed to initialize RabbitMQ listener")
            raise MessagingError("Failed to initialize RabbitMQ listener") from e

    def _callback(self,
                  ch,
                  method,
                  properties,
                  body) -> None:
        try:
            message = json.loads(body)
            document_id = message.get("document_id")
            logger.info(f"Received document_id={document_id}")

            with self.db_session_manager.get_session() as db:
                service = IngestionService(
                    document_repository=DocumentRepository(),
                    fragment_repository=FragmentRepository(),
                    storage_service=MinioStorageService(),
                )
                service.process_document(document_id, db)

            ch.basic_ack(delivery_tag=method.delivery_tag)
            logger.info(f"✅ Document {document_id} processed successfully")

        except Exception as e:
            logger.exception(f"Error processing message: {e}")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

    def start_consuming(self) -> None:
        try:
            self.channel.basic_consume(
                queue=environment_variables.queue,
                on_message_callback=self._callback,
                auto_ack=False
            )
            logger.info(f"Waiting for messages in '{environment_variables.queue}'...")
            self.channel.start_consuming()
        except Exception as e:
            logger.exception("Error while consuming messages")
            raise MessagingError("Error while consuming messages") from e

    def close(self) -> None:
        try:
            if self.connection and not self.connection.is_closed:
                self.connection.close()
                logger.info("RabbitMQ connection closed.")
        except Exception as e:
            logger.warning("Error closing RabbitMQ connection", exc_info=e)