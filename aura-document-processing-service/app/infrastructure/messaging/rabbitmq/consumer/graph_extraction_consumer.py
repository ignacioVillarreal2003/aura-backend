import logging
from typing import Optional

from app.application.services.graph.graph_extraction_service.interfaces.graph_extraction_service_interface import (
    GraphExtractionServiceInterface,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.infrastructure.messaging.rabbitmq.consumer.base_consumer import BaseConsumer
from app.infrastructure.messaging.rabbitmq.consumer.interfaces.graph_extraction_consumer_interface import (
    GraphExtractionConsumerInterface,
)
from app.infrastructure.messaging.rabbitmq.dtos.commands.graph_extraction_command import GraphExtractionCommand
from app.infrastructure.messaging.rabbitmq.dtos.envelope.message_envelope import MessageEnvelope
from app.infrastructure.messaging.rabbitmq.rabbitmq_manager_interface import RabbitMQManagerInterface

logger = logging.getLogger(__name__)


class GraphExtractionConsumer(BaseConsumer[GraphExtractionCommand], GraphExtractionConsumerInterface):
    def __init__(
            self,
            rabbitmq_manager: RabbitMQManagerInterface,
            graph_extraction_service: GraphExtractionServiceInterface,
    ) -> None:
        super().__init__(rabbitmq_manager)
        self._service = graph_extraction_service

    @property
    def _queue_name(self) -> str:
        return self._settings.graph_extraction_queue

    @property
    def _prefetch_count(self) -> Optional[int]:
        return 1

    def _get_command_type(self) -> type[GraphExtractionCommand]:
        return GraphExtractionCommand

    async def _process(self, envelope: MessageEnvelope[GraphExtractionCommand]) -> None:
        command = envelope.command
        user = AuthenticatedUser.model_validate(command.user)
        await self._service.extract_for_document(
            document_id=command.document_id,
            user=user,
            force=command.force,
            message_id=envelope.message_id,
        )
        logger.info(
            "The graph-extraction message was processed.",
            extra={
                "message_id": envelope.message_id,
                "document_id": command.document_id,
                "user_id": user.id,
            },
        )
