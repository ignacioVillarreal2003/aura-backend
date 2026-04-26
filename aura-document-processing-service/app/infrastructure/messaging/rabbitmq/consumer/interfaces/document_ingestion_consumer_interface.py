from abc import ABC, abstractmethod

from app.infrastructure.messaging.rabbitmq.consumer.interfaces.consumer_interface import ConsumerInterface
from app.infrastructure.messaging.rabbitmq.dtos.commands.document_ingestion_command import DocumentIngestionCommand
from app.infrastructure.messaging.rabbitmq.dtos.envelope.message_envelope import MessageEnvelope


class DocumentIngestionConsumerInterface(ConsumerInterface, ABC):
    @abstractmethod
    async def handle(
            self,
            message_envelope: MessageEnvelope[DocumentIngestionCommand]
    ) -> None:
        pass
