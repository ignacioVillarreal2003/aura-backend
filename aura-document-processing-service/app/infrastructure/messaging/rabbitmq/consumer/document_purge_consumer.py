import logging
from typing import Optional

from app.infrastructure.messaging.rabbitmq.consumer.base_consumer import BaseConsumer
from app.infrastructure.messaging.rabbitmq.consumer.interfaces.document_purge_consumer_interface import (
    DocumentPurgeConsumerInterface,
)
from app.infrastructure.messaging.rabbitmq.dtos.commands.document_purge_command import DocumentPurgeCommand
from app.infrastructure.messaging.rabbitmq.dtos.envelope.message_envelope import MessageEnvelope
from app.infrastructure.messaging.rabbitmq.rabbitmq_manager_interface import RabbitMQManagerInterface
from app.infrastructure.persistence.database.database_manager.database_manager_interface import (
    DatabaseManagerInterface,
)
from app.infrastructure.persistence.database.repositories.document_repository.document_repository_interface import (
    DocumentRepositoryInterface,
)
from app.infrastructure.persistence.graph.repositories.graph_entity_repository.graph_entity_repository_interface import (
    GraphEntityRepositoryInterface,
)
from app.infrastructure.persistence.graph.repositories.graph_relation_repository.graph_relation_repository_interface import (
    GraphRelationRepositoryInterface,
)
from app.infrastructure.persistence.storages.document_storage.document_storage_exception import (
    DocumentNotFoundException,
)
from app.infrastructure.persistence.storages.document_storage.document_storage_interface import (
    DocumentStorageInterface,
)

logger = logging.getLogger(__name__)


class DocumentPurgeConsumer(BaseConsumer[DocumentPurgeCommand], DocumentPurgeConsumerInterface):
    """Purges a soft-deleted document's footprint from the external systems.

    Postgres keeps the document and its fragments soft-deleted (already excluded
    from search). This consumer reclaims the rest of the footprint that the soft
    delete leaves behind: the object in MinIO and the entity/relation provenance
    in Neo4j. It is driven by a queue so the delete request stays fast and the
    cleanup is retried (dead-letter) on partial failure. Every step is idempotent,
    so a redelivery is safe.
    """

    def __init__(
            self,
            rabbitmq_manager: RabbitMQManagerInterface,
            database_manager: DatabaseManagerInterface,
            document_repository: DocumentRepositoryInterface,
            document_storage: DocumentStorageInterface,
            graph_entity_repository: Optional[GraphEntityRepositoryInterface] = None,
            graph_relation_repository: Optional[GraphRelationRepositoryInterface] = None,
    ) -> None:
        super().__init__(rabbitmq_manager)
        self._database_manager = database_manager
        self._document_repository = document_repository
        self._document_storage = document_storage
        self._graph_entity_repository = graph_entity_repository
        self._graph_relation_repository = graph_relation_repository

    @property
    def _queue_name(self) -> str:
        return self._settings.document_purge_queue

    @property
    def _prefetch_count(self) -> Optional[int]:
        return 1

    def _get_command_type(self) -> type[DocumentPurgeCommand]:
        return DocumentPurgeCommand

    async def _process(self, envelope: MessageEnvelope[DocumentPurgeCommand]) -> None:
        command = envelope.command

        if not await self._is_safe_to_purge(command.document_id):
            logger.warning(
                "Skipping purge: the document is not soft-deleted (stale or rolled-back delete).",
                extra={"message_id": envelope.message_id, "document_id": command.document_id},
            )
            return

        await self._purge_storage_object(
            document_id=command.document_id,
            storage_url=command.storage_url,
        )
        await self._purge_graph_footprint(document_id=command.document_id)

        logger.info(
            "The document-purge message was processed.",
            extra={
                "message_id": envelope.message_id,
                "document_id": command.document_id,
            },
        )

    async def _is_safe_to_purge(self, document_id: int) -> bool:
        """Confirm the document is actually gone before reclaiming its footprint.

        Purging MinIO and Neo4j is irreversible, so we never act on a live row. A
        missing row is safe to purge (already hard-deleted upstream); a row with no
        ``deleted_at`` means the delete never committed and must not be purged.
        """
        async with self._database_manager.session() as session:
            document = await self._document_repository.get_document_by_id_including_deleted(
                document_id=document_id,
                database_session=session,
            )
        if document is None:
            return True
        return document.deleted_at is not None

    async def _purge_storage_object(self, *, document_id: int, storage_url: str) -> None:
        try:
            await self._document_storage.delete_document(storage_url)
        except DocumentNotFoundException:
            # Already gone (e.g. a redelivery after a prior successful purge). Treat
            # as success so the rest of the purge can complete and the message acks.
            logger.info(
                "The storage object was already absent during purge.",
                extra={"document_id": document_id},
            )

    async def _purge_graph_footprint(self, *, document_id: int) -> None:
        if self._graph_relation_repository is None or self._graph_entity_repository is None:
            logger.warning(
                "Knowledge graph is not wired in this instance; skipping graph purge.",
                extra={"document_id": document_id},
            )
            return

        # Relations first so relation provenance is corrected even for relations
        # whose endpoint entities survive; then orphaned entities (DETACH DELETE).
        await self._graph_relation_repository.delete_document_relations(document_id=document_id)
        await self._graph_entity_repository.delete_document_entities(document_id=document_id)
