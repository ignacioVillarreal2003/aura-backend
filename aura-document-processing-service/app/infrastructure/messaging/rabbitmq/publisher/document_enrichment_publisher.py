import logging
from typing import Optional

from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.infrastructure.http.authentication_provider.request_token import get_request_token
from app.infrastructure.messaging.rabbitmq.dtos.commands.document_enrichment_command import (
    DocumentEnrichmentCommand,
)
from app.infrastructure.messaging.rabbitmq.dtos.envelope.message_envelope import MessageEnvelope
from app.infrastructure.messaging.rabbitmq.publisher.interfaces.document_enrichment_publisher_interface import (
    DocumentEnrichmentPublisherInterface,
)
from app.infrastructure.messaging.rabbitmq.interfaces.rabbitmq_manager_interface import RabbitMQManagerInterface
from app.infrastructure.messaging.rabbitmq.reliable_publish.redis_outbox_lite import RedisOutboxLite

logger = logging.getLogger(__name__)


class DocumentEnrichmentPublisher(DocumentEnrichmentPublisherInterface):
    def __init__(
            self,
            rabbitmq_manager: RabbitMQManagerInterface,
            outbox_lite: Optional[RedisOutboxLite] = None,
    ) -> None:
        self._manager = rabbitmq_manager
        self._settings = rabbitmq_manager.settings
        self._outbox_lite = outbox_lite

    async def publish(
            self,
            *,
            document_id: int,
            user: AuthenticatedUser,
            batch_id: Optional[str] = None,
    ) -> str:
        envelope = MessageEnvelope.wrap(
            DocumentEnrichmentCommand(
                document_id=document_id,
                user=user.model_dump(mode="json"),
                batch_id=batch_id,
                auth_token=get_request_token(),
            )
        )
        headers = {
            "message_id": envelope.message_id,
            "correlation_id": str(document_id),
        }
        if self._outbox_lite is not None:
            await self._outbox_lite.publish_or_enqueue(
                event_id=envelope.message_id,
                event_type="document_enrichment",
                aggregate_id=str(document_id),
                routing_key=self._settings.document_enrichment_queue,
                body=envelope.to_bytes(),
                exchange_name=self._settings.exchange,
                headers=headers,
            )
        else:
            await self._manager.publish(
                routing_key=self._settings.document_enrichment_queue,
                body=envelope.to_bytes(),
                exchange_name=self._settings.exchange,
                headers=headers,
            )

        logger.info(
            "A document-enrichment command was published.",
            extra={
                "document_id": document_id,
                "message_id": envelope.message_id,
            },
        )
        return envelope.message_id
