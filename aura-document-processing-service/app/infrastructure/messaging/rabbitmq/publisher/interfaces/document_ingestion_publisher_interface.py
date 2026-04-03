from abc import ABC, abstractmethod

from app.infrastructure.messaging.rabbitmq.dtos.commands.document_ingestion_command import DocumentIngestionCommand


class DocumentIngestionPublisherInterface(ABC):
    @abstractmethod
    async def publish(
            self,
            document_ingestion_command: DocumentIngestionCommand
    ) -> str:
        pass
