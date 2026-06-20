import logging
from typing import Optional

from fastapi import HTTPException, Request, status

from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.infrastructure.http.authentication_provider.request_token import get_request_token
from app.infrastructure.messaging.rabbitmq.dtos.commands.graph_extraction_command import (
    GraphExtractionCommand,
)
from app.infrastructure.messaging.rabbitmq.dtos.envelope.message_envelope import MessageEnvelope
from app.infrastructure.messaging.rabbitmq.publisher.interfaces.graph_extraction_publisher_interface import (
    GraphExtractionPublisherInterface,
)
from app.infrastructure.messaging.rabbitmq.interfaces.rabbitmq_manager_interface import RabbitMQManagerInterface
from app.infrastructure.messaging.rabbitmq.reliable_publish.redis_outbox_lite import RedisOutboxLite

logger = logging.getLogger(__name__)


class GraphExtractionPublisher(GraphExtractionPublisherInterface):
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
            GraphExtractionCommand(
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
            },
        )
        return envelope.message_id


async def get_graph_extraction_publisher(
        request: Request,
) -> GraphExtractionPublisherInterface:
    publisher = getattr(request.app.state, "graph_extraction_publisher", None)
    if publisher is None:
        logger.error("GraphExtractionPublisher is not registered on the application state.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Knowledge graph extraction publisher is not available.",
        )
    return publisher
