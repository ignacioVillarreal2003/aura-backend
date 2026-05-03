import logging
from typing import Optional

from app.configuration.graph.knowledge_graph_settings import KnowledgeGraphSettings
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.types import UserId
from app.infrastructure.messaging.rabbitmq.dtos.commands.graph_extraction_command import (
    GraphExtractionCommand,
)
from app.infrastructure.messaging.rabbitmq.dtos.envelope.message_envelope import MessageEnvelope
from app.infrastructure.messaging.rabbitmq.publisher.interfaces.graph_extraction_publisher_interface import (
    GraphExtractionPublisherInterface,
)
from app.infrastructure.messaging.rabbitmq.rabbitmq_manager_interface import RabbitMQManagerInterface
from app.infrastructure.messaging.rabbitmq.reliable_publish.redis_outbox_lite import RedisOutboxLite

logger = logging.getLogger(__name__)


class GraphExtractionPublisher(GraphExtractionPublisherInterface):
    def __init__(
            self,
            rabbitmq_manager: RabbitMQManagerInterface,
            knowledge_graph_settings: Optional[KnowledgeGraphSettings] = None,
            outbox_lite: Optional[RedisOutboxLite] = None,
    ) -> None:
        self._manager = rabbitmq_manager
        self._settings = rabbitmq_manager.settings
        self._knowledge_graph_settings = knowledge_graph_settings or KnowledgeGraphSettings()
        self._outbox_lite = outbox_lite

    async def publish(
            self,
            *,
            document_id: int,
            user: AuthenticatedUser,
            force: bool = False,
    ) -> str:
        envelope = MessageEnvelope.wrap(
            GraphExtractionCommand(
                document_id=document_id,
                user=user.model_dump(mode="json"),
                force=force,
            )
        )
        headers = {
            "message_id": envelope.message_id,
            "correlation_id": str(document_id),
        }
        if self._outbox_lite is not None:
            await self._outbox_lite.publish_or_enqueue(
                event_id=envelope.message_id,
                event_type="graph_extraction",
                aggregate_id=str(document_id),
                routing_key=self._settings.graph_extraction_queue,
                body=envelope.to_bytes(),
                exchange_name=self._settings.exchange,
                headers=headers,
            )
        else:
            await self._manager.publish(
                routing_key=self._settings.graph_extraction_queue,
                body=envelope.to_bytes(),
                exchange_name=self._settings.exchange,
                headers=headers,
            )

        logger.info(
            "A graph-extraction command was published.",
            extra={
                "document_id": document_id,
                "message_id": envelope.message_id,
                "force": force,
            },
        )
        return envelope.message_id

    async def publish_for_document_owner(
            self,
            *,
            document_id: int,
            owner_user_id: int,
            force: bool = False,
    ) -> str:
        principal = AuthenticatedUser(
            id=UserId(int(owner_user_id)),
            email=self._knowledge_graph_settings.system_principal_email,
            roles=self._knowledge_graph_settings.resolve_system_principal_roles(),
            permissions=self._knowledge_graph_settings.resolve_system_principal_permissions(),
        )
        return await self.publish(
            document_id=document_id,
            user=principal,
            force=force,
        )
