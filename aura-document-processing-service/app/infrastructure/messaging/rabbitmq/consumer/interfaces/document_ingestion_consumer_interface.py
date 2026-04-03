from abc import ABC, abstractmethod

from app.infrastructure.messaging.rabbitmq.dtos.commands.document_ingestion_command import DocumentIngestionCommand
from app.infrastructure.messaging.rabbitmq.dtos.envelope.message_envelope import MessageEnvelope


class DocumentIngestionConsumerInterface(ABC):
    @abstractmethod
    async def start(
            self
    ) -> None:
        pass

    @abstractmethod
    async def handle(
            self,
            message_envelope: MessageEnvelope[DocumentIngestionCommand]
    ) -> None:
        pass
