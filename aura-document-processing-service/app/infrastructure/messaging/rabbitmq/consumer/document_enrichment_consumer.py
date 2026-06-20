import logging
from typing import Optional

from app.application.services.document.document_enrichment_service.interfaces.document_enrichment_service_interface import (
    DocumentEnrichmentServiceInterface,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.constants.document.bulk_operation import BulkOperation
from app.infrastructure.messaging.rabbitmq.consumer.base_consumer import BaseConsumer
from app.infrastructure.messaging.rabbitmq.consumer.bulk_progress_mixin import BulkProgressMixin
from app.infrastructure.messaging.rabbitmq.consumer.interfaces.document_enrichment_consumer_interface import (
    DocumentEnrichmentConsumerInterface,
)
from app.infrastructure.persistence.memory_database.bulk_job_progress_store.interfaces.bulk_job_progress_store_interface import (
    BulkJobProgressStoreInterface,
)
from app.infrastructure.messaging.rabbitmq.dtos.commands.document_enrichment_command import DocumentEnrichmentCommand
from app.infrastructure.messaging.rabbitmq.dtos.envelope.message_envelope import MessageEnvelope
from app.infrastructure.messaging.rabbitmq.interfaces.rabbitmq_manager_interface import RabbitMQManagerInterface

logger = logging.getLogger(__name__)


class DocumentEnrichmentConsumer(
    BulkProgressMixin,
    BaseConsumer[DocumentEnrichmentCommand],
    DocumentEnrichmentConsumerInterface,
):
    _bulk_operation = BulkOperation.enrich

    def __init__(
            self,
            rabbitmq_manager: RabbitMQManagerInterface,
            document_enrichment_service: DocumentEnrichmentServiceInterface,
            bulk_job_progress_store: Optional[BulkJobProgressStoreInterface] = None,
    ) -> None:
        super().__init__(rabbitmq_manager)
        self._service = document_enrichment_service
        self._bulk_store = bulk_job_progress_store

    @property
    def _queue_name(self) -> str:
        return self._settings.document_enrichment_queue

    @property
    def _prefetch_count(self) -> Optional[int]:
        return 1

    def _get_command_type(self) -> type[DocumentEnrichmentCommand]:
        return DocumentEnrichmentCommand

    async def _execute(self, envelope: MessageEnvelope[DocumentEnrichmentCommand]) -> None:
        command = envelope.command
        user = AuthenticatedUser.model_validate(command.user)
        await self._service.enrich_for_document(
            document_id=command.document_id,
            user=user,
        )
        logger.info(
            "The document-enrichment message was processed.",
            extra={
                "message_id": envelope.message_id,
                "document_id": command.document_id,
                "user_id": user.id,
            },
        )
