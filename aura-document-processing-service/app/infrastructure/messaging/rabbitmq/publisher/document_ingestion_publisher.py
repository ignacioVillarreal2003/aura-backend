import logging

from app.infrastructure.messaging.rabbitmq.dtos.commands.document_ingestion_command import DocumentIngestionCommand
from app.infrastructure.messaging.rabbitmq.dtos.envelope.message_envelope import MessageEnvelope
from app.infrastructure.messaging.rabbitmq.rabbitmq_manager_interface import RabbitMQManagerInterface
from app.infrastructure.messaging.rabbitmq.publisher.interfaces.document_ingestion_publisher_interface import (
    DocumentIngestionPublisherInterface
)

logger = logging.getLogger(__name__)


class DocumentIngestionPublisher(DocumentIngestionPublisherInterface):
    def __init__(
            self,
            rabbitmq_manager: RabbitMQManagerInterface
    ) -> None:
        self._manager = rabbitmq_manager
        self._settings = rabbitmq_manager.settings

    async def publish(
            self,
            document_ingestion_command: DocumentIngestionCommand
    ) -> str:
        message_envelope = MessageEnvelope.wrap(document_ingestion_command)

        await self._manager.publish(
            routing_key=self._settings.document_ingestion_queue,
            body=message_envelope.to_bytes(),
            exchange_name=self._settings.exchange,
            headers={
                "message_id": message_envelope.message_id,
                "version": str(message_envelope.version)
            }
        )

        logger.info(
            "A document ingestion command was published to the queue.",
            extra={
                "message_id": message_envelope.message_id,
                "document_id": document_ingestion_command.document_id
            }
        )

        return message_envelope.message_id
