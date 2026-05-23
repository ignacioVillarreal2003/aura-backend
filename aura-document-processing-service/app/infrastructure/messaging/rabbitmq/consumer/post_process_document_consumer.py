import logging

from app.application.services.document.post_process_document_service.interfaces.post_process_document_processor_interface import (
    PostProcessDocumentProcessorInterface,
)
from app.infrastructure.messaging.rabbitmq.consumer.base_consumer import BaseConsumer
from app.infrastructure.messaging.rabbitmq.consumer.interfaces.post_process_document_consumer_interface import (
    PostProcessDocumentConsumerInterface,
)
from app.infrastructure.messaging.rabbitmq.dtos.commands.post_process_document_job_command import (
    PostProcessDocumentJobCommand,
)
from app.infrastructure.messaging.rabbitmq.dtos.envelope.message_envelope import MessageEnvelope
from app.infrastructure.messaging.rabbitmq.rabbitmq_manager_interface import RabbitMQManagerInterface

logger = logging.getLogger(__name__)


class PostProcessDocumentConsumer(BaseConsumer[PostProcessDocumentJobCommand], PostProcessDocumentConsumerInterface):
    def __init__(
            self,
            rabbitmq_manager: RabbitMQManagerInterface,
            processor: PostProcessDocumentProcessorInterface,
    ) -> None:
        super().__init__(rabbitmq_manager)
        self._processor = processor

    def _get_command_type(self) -> type[PostProcessDocumentJobCommand]:
        return PostProcessDocumentJobCommand

    async def _process(self, envelope: MessageEnvelope[PostProcessDocumentJobCommand]) -> None:
        job_id = envelope.command.job_id
        logger.info(
            "Running the document post-process job.",
            extra={"message_id": envelope.message_id, "job_id": job_id},
        )
        await self._processor.run_job(job_id)

    async def start(self) -> None:
        await self._manager.start_consumer(
            queue_name=self._settings.post_process_document_queue,
            callback=self._handle_message,
            prefetch_count=1,
        )
        logger.info(
            "The document post-process consumer was registered on the queue.",
            extra={"queue": self._settings.post_process_document_queue},
        )
