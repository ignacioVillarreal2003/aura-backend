import logging

from app.infrastructure.messaging.rabbitmq.dtos.commands.post_process_fragment_job_command import (
    PostProcessFragmentJobCommand,
)
from app.infrastructure.messaging.rabbitmq.dtos.envelope.message_envelope import MessageEnvelope
from app.infrastructure.messaging.rabbitmq.publisher.interfaces.post_process_fragment_job_publisher_interface import (
    PostProcessFragmentJobPublisherInterface,
)
from app.infrastructure.messaging.rabbitmq.rabbitmq_manager_interface import RabbitMQManagerInterface

logger = logging.getLogger(__name__)


class PostProcessFragmentJobPublisher(PostProcessFragmentJobPublisherInterface):
    def __init__(
            self,
            rabbitmq_manager: RabbitMQManagerInterface,
    ) -> None:
        self._manager = rabbitmq_manager
        self._settings = rabbitmq_manager.settings

    async def publish_job(
            self,
            job_id: str,
    ) -> str:
        envelope = MessageEnvelope.wrap(PostProcessFragmentJobCommand(job_id=job_id))
        await self._manager.publish(
            routing_key=self._settings.post_process_fragment_queue,
            body=envelope.to_bytes(),
            exchange_name=self._settings.exchange,
            headers={
                "message_id": envelope.message_id,
                "correlation_id": job_id,
            },
        )
        logger.info(
            "A fragment post-process job was published.",
            extra={"job_id": job_id, "message_id": envelope.message_id},
        )
        return envelope.message_id
