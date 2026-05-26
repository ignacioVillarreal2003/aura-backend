import logging

from app.application.services.fragment.post_process_fragment_service.interfaces.post_process_fragment_processor_interface import (
    PostProcessFragmentProcessorInterface,
)
from app.infrastructure.messaging.rabbitmq.consumer.base_consumer import BaseConsumer
from app.infrastructure.messaging.rabbitmq.consumer.interfaces.post_process_fragment_consumer_interface import (
    PostProcessFragmentConsumerInterface,
)
from app.infrastructure.messaging.rabbitmq.dtos.commands.post_process_fragment_job_command import (
    PostProcessFragmentJobCommand,
)
from app.infrastructure.messaging.rabbitmq.dtos.envelope.message_envelope import MessageEnvelope
from app.infrastructure.messaging.rabbitmq.rabbitmq_manager_interface import RabbitMQManagerInterface

logger = logging.getLogger(__name__)


class PostProcessFragmentConsumer(BaseConsumer[PostProcessFragmentJobCommand], PostProcessFragmentConsumerInterface):
    def __init__(
            self,
            rabbitmq_manager: RabbitMQManagerInterface,
            processor: PostProcessFragmentProcessorInterface,
    ) -> None:
        super().__init__(rabbitmq_manager)
        self._processor = processor

    def _get_command_type(self) -> type[PostProcessFragmentJobCommand]:
        return PostProcessFragmentJobCommand

    async def _process(self, envelope: MessageEnvelope[PostProcessFragmentJobCommand]) -> None:
        job_id = envelope.command.job_id
        logger.info(
            "Running the fragment post-process job.",
            extra={"message_id": envelope.message_id, "job_id": job_id},
        )
        await self._processor.run_job(job_id)

    async def start(self) -> None:
        await self._manager.start_consumer(
            queue_name=self._settings.post_process_fragment_queue,
            callback=self._handle_message,
            prefetch_count=1,
        )
        logger.info(
            "The fragment post-process consumer was registered on the queue.",
            extra={"queue": self._settings.post_process_fragment_queue},
        )
